"""Stage 8: choose zero or more verified Act 1 sigils.

A sigil is eligible only when the subject's identity has a matching trait
(e.g. 'flight' -> Airborne) or a named physical rule from interpretation.py holds
(e.g. 'passive_spines' -> Sharp Quills). A texture keyword on its own is never
enough. Confidence limits how many are kept, and conflicting or degenerate
combinations from data/sigils.json are skipped.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .config import balance_rules, selectable_sigils, sigil_table, size_rank
from .interpretation import PhysicalProfile
from .taxonomy import Identification


@dataclass
class SigilChoice:
    id: str
    display_name: str
    power: int
    category: str
    priority: int
    signature: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def conflict_reason(a: str, b: str) -> str | None:
    """Why two ability ids may not share a card, or None if they may."""
    table = sigil_table()
    for group, members in table["exclusive_groups"].items():
        if a in members and b in members:
            return f"both are in the exclusive group '{group}'"
    for rule in table["forbidden_pairs"]:
        if {a, b} == set(rule["pair"]):
            return rule["reason"]
    return None


def eligible_sigils(ident: Identification, profile: PhysicalProfile, tribe: str) -> tuple[list[SigilChoice], list[str]]:
    """Every allowlisted sigil this subject could justify, plus notes on near-misses."""
    eligible: list[SigilChoice] = []
    skipped: list[str] = []
    traits = set(ident.traits)
    for entry in selectable_sigils().values():
        kinds = entry["subject_kinds"]
        trait_hit = sorted(traits & set(entry.get("requires_any_trait", [])))
        rule = entry.get("physical_rule")
        rule_hit = bool(rule) and profile.rule(rule)
        if not (trait_hit or rule_hit):
            continue
        if ident.kind not in kinds:
            skipped.append(f"{entry['display_name']}: not available to {ident.kind} subjects")
            continue
        if "min_size" in entry and size_rank(profile.size) < size_rank(entry["min_size"]):
            skipped.append(f"{entry['display_name']}: subject is smaller than {entry['min_size']}")
            continue
        if trait_hit:
            reason = f"{ident.matched_phrase or ident.object_name} has trait {trait_hit}"
        else:
            reason = f"physical rule '{rule}': {profile.interpretation.get(rule, rule)}"
        eligible.append(SigilChoice(entry["id"], entry["display_name"], entry["power"], entry["category"],
                                    entry["priority"], tribe in entry.get("signature_for", []), reason))
    return eligible, skipped


def select_sigils(eligible: list[SigilChoice], confidence: str, variant: int = 0) -> tuple[list[SigilChoice], list[str]]:
    """Pick up to the confidence-limited number of non-conflicting sigils.

    Tribe signature sigils (Airborne for birds, Sprinter-family for hooved) go first,
    then the remaining candidates by priority. ``variant`` rotates the non-signature
    candidates so the CLI's --variants option offers genuinely different cards.
    """
    rules = balance_rules()
    limit = min(rules["max_sigils"], rules["confidence"][confidence]["max_sigils"])
    notes: list[str] = []
    if limit == 0:
        if eligible:
            notes.append(f"{confidence} confidence: no sigils (eligible were {[s.display_name for s in eligible]})")
        return [], notes

    signature = sorted([s for s in eligible if s.signature], key=lambda s: (-s.priority, s.id))
    rest = sorted([s for s in eligible if not s.signature], key=lambda s: (-s.priority, s.id))
    if rest and variant:
        shift = variant % len(rest)
        rest = rest[shift:] + rest[:shift]

    chosen: list[SigilChoice] = []
    for candidate in signature[:1] + rest + signature[1:]:
        if len(chosen) >= limit:
            notes.append(f"{candidate.display_name}: skipped, card already has {limit} sigil(s)")
            continue
        clash = next((conflict_reason(c.id, candidate.id) for c in chosen if conflict_reason(c.id, candidate.id)), None)
        if clash:
            notes.append(f"{candidate.display_name}: skipped ({clash})")
            continue
        chosen.append(candidate)
    return chosen, notes
