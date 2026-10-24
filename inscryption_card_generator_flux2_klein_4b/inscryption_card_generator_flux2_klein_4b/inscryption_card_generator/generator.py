"""Card design: image-analysis JSON -> balanced, validated GeneratedCard.

Pipeline stages (numbers match the project brief):
 3 normalize JSON          analysis.normalize_analysis
 4 identify subject        taxonomy.identify_subject
 5 assign tribe            taxonomy.assign_tribe
 6 interpret properties    interpretation.interpret + stats.estimate_stats
 7 name and description    naming
 8 select sigils           sigils.eligible_sigils / select_sigils
 9 blood cost              balance.required_blood_cost
10-11 validate and correct balance.balance_design (+ conservative fallback)
"""
from __future__ import annotations

from typing import Any, Callable

from . import ai_proposer
from .analysis import NormalizedAnalysis, normalize_analysis
from .balance import (CardValidationError, balance_design, effective_attack, power_breakdown,
                      required_blood_cost, sigil_errors, vanilla_cp_range)
from .card_models import GeneratedCard
from .config import balance_rules, selectable_sigils
from .interpretation import interpret
from .naming import build_description, choose_display_name, make_card_id
from .sigils import eligible_sigils, select_sigils
from .stats import estimate_stats
from .taxonomy import Identification, assign_tribe, confidence_after_identification, identify_subject


def _sigil_records(ids: list[str], reasons: dict[str, str]) -> list[dict[str, Any]]:
    allow = selectable_sigils()
    return [{"id": s, "display_name": allow[s]["display_name"], "power": allow[s]["power"],
             "effect": allow[s]["effect"], "reason": reasons.get(s, "")} for s in ids]


def _checks(card: dict[str, Any], ident: Identification, taxonomy_tribe: str, bonus_by_field: dict[str, int]) -> dict[str, dict[str, Any]]:
    rules = balance_rules()
    b = rules["stat_bounds"]
    a, h, sigils, tribe, cost = card["attack"], card["health"], card["sigils"], card["tribe"], card["blood_cost"]
    required, _ = required_blood_cost(a, h, sigils, tribe)
    combo_errors = sigil_errors(sigils)
    cp = power_breakdown(a, h, sigils)["total"]
    vanilla = vanilla_cp_range(cost) if cost is not None else None
    worst = max(bonus_by_field.values(), default=0)
    tribe_ok = (tribe == "Miscellaneous") if not ident.is_animal else tribe in {taxonomy_tribe, "Miscellaneous"}
    return {
        "1_stat_ranges": {"passed": b["attack_min"] <= a <= b["attack_max"] and b["health_min"] <= h <= b["health_max"],
                          "detail": f"{a}/{h} within attack {b['attack_min']}-{b['attack_max']}, health {b['health_min']}-{b['health_max']}"},
        "2_cost_matches_power": {"passed": cost is not None and cost == required,
                                 "detail": f"CP {cp} -> {required} blood (card has {cost})"},
        "3_sigil_combination": {"passed": not combo_errors and effective_attack(a, sigils) <= rules["max_effective_attack"],
                                "detail": "; ".join(combo_errors) or
                                          f"{len(sigils)} allowlisted sigil(s), no forbidden pairs, effective attack {effective_attack(a, sigils)}"},
        "4_no_single_attribute_dominates": {"passed": worst <= 2,
                                            "detail": f"largest CP bonus from one JSON field is {worst} (limit 2): {bonus_by_field or 'none'}"},
        "5_tribe_appropriate": {"passed": tribe_ok,
                                "detail": f"{ident.kind} subject -> {tribe}"},
        "6_plausible_in_card_pool": {"passed": vanilla is None or vanilla[0] <= cp <= vanilla[1],
                                     "detail": f"CP {cp}; vanilla commons at {cost} blood span {vanilla}"},
    }


def design_card(source: Any, variant: int = 0, *, strict: bool = False, use_ai: bool = False,
                ai_chat: Callable[..., Any] | None = None) -> GeneratedCard:
    """Design one card from analyzer output (JSON text, dict, or pydantic model)."""
    analysis: NormalizedAnalysis = normalize_analysis(source)
    ident = identify_subject(analysis)
    diagnostics: dict[str, Any] = {"normalized_analysis": {k: v for k, v in analysis.to_dict().items() if k != "raw"},
                                   "identification": ident.to_dict()}

    if not ident.supported:
        name = choose_display_name(ident, variant)
        if strict:
            raise CardValidationError(ident.reasons)
        return GeneratedCard(
            card_id=make_card_id(name, analysis.raw, variant), display_name=name, description="",
            object_name=analysis.object_name, subject_kind=ident.kind, tribe="Miscellaneous", game_tribes=[],
            attack=0, health=1, blood_cost=None, sigils=[], card_power={}, source_attributes=analysis.raw,
            validation_status="rejected", validation={"errors": ident.reasons, "warnings": [], "adjustments": [], "checks": {}},
            rescan_recommended=True, variant=variant, diagnostics=diagnostics)

    confidence, conf_notes = confidence_after_identification(ident, analysis.effective_confidence)
    tribe = assign_tribe(ident, confidence)
    profile = interpret(analysis, ident)
    estimate = estimate_stats(ident, profile, tribe.tribe, confidence)
    eligible, skipped = eligible_sigils(ident, profile, tribe.tribe)
    chosen, selection_notes = select_sigils(eligible, confidence, variant)

    attack, health = estimate.attack, estimate.health
    sigil_ids = [c.id for c in chosen]
    reasons = {c.id: c.reason for c in eligible}
    notes = list(conf_notes)
    allow = selectable_sigils()
    if estimate.protective_bonus_applied and any(allow[s].get("consumes_evidence") == "protective_structure" for s in sigil_ids):
        health -= balance_rules()["health_model"]["protective_structure_bonus"]
        notes.append("shell evidence is represented by Armored, so its +1 health is removed (no double counting)")

    accepted: dict[str, Any] = {}
    if use_ai:
        try:
            prompt = ai_proposer.build_prompt(analysis, ident, tribe.tribe, eligible, attack, health)
            accepted, ai_notes = ai_proposer.sanitize_proposal(ai_proposer.request_proposal(prompt, chat=ai_chat),
                                                               eligible, attack, health)
            notes += ai_notes
            attack, health = accepted.get("attack", attack), accepted.get("health", health)
            if "sigils" in accepted:
                limit = balance_rules()["confidence"][confidence]["max_sigils"]
                sigil_ids = accepted["sigils"][:limit]
                for s in sigil_ids:
                    reasons.setdefault(s, "proposed by the AI and eligible under the rules")
        except ai_proposer.ProposalError as exc:
            notes.append(f"AI proposal unavailable, deterministic design used: {exc}")

    priorities = {c.id: c.priority for c in eligible}
    protected = {c.id for c in chosen if c.signature}
    result = balance_design(attack, health, sigil_ids, tribe.tribe, priorities, protected, ident.kind)
    status = result.status
    errors, warnings, adjustments = list(result.errors), list(result.warnings), list(result.adjustments)

    if status == "rejected":
        if strict:
            raise CardValidationError(errors or ["design could not be balanced"])
        fallback = balance_design(0, min(estimate.health, 3), [], tribe.tribe, subject_kind=ident.kind)
        adjustments.append(f"design rejected ({'; '.join(errors)}); replaced by a conservative fallback")
        result, status, errors, warnings = fallback, ("fallback" if fallback.status != "rejected" else "rejected"), \
            fallback.errors, fallback.warnings

    rescan = bool(balance_rules()["confidence"][confidence].get("rescan_recommended"))
    if status in {"valid", "adjusted"} and confidence == "low":
        status = "conservative"

    name = accepted.get("display_name") or choose_display_name(ident, variant)
    description = accepted.get("description") or build_description(name, ident, tribe.tribe, result.sigils, profile)
    card_view = {"attack": result.attack, "health": result.health, "sigils": result.sigils,
                 "tribe": tribe.tribe, "blood_cost": result.blood_cost}
    checks = _checks(card_view, ident, ident.taxonomy_tribe, estimate.bonus_power_by_field)

    diagnostics.update({
        "confidence": {"reported": analysis.confidence, "after_normalization": analysis.effective_confidence,
                       "used": confidence},
        "tribe_reason": tribe.reason,
        "physical_profile": profile.to_dict(),
        "stat_estimate": estimate.to_dict(),
        "sigil_eligibility": [c.to_dict() for c in eligible],
        "sigil_skipped": skipped + selection_notes,
        "notes": notes,
    })
    return GeneratedCard(
        card_id=make_card_id(name, analysis.raw, variant), display_name=name, description=description,
        object_name=analysis.object_name, subject_kind=ident.kind, tribe=tribe.tribe, game_tribes=tribe.game_tribes,
        attack=result.attack, health=result.health, blood_cost=result.blood_cost,
        sigils=_sigil_records(result.sigils, reasons), card_power=power_breakdown(result.attack, result.health, result.sigils),
        source_attributes=analysis.raw, validation_status=status,
        validation={"errors": errors, "warnings": warnings, "adjustments": adjustments, "checks": checks},
        rescan_recommended=rescan, variant=variant, diagnostics=diagnostics)
