"""Stages 9-11: card power, blood cost, validation and correction.

Card Power (CP) = sum(sigil power) + health + 2 * attack (+ combo surcharges).
Blood cost is the cheapest band in data/balance_rules.json whose CP ceiling and
extra limits the card satisfies. The bands reproduce every non-outlier vanilla
blood-cost common in the calibration set (tests/test_balance.py).

``validate_design`` reports problems; ``balance_design`` fixes what it can in a
fixed, documented order and marks anything it cannot fix as rejected. Nothing
(including an AI proposal) reaches the export without passing through here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .config import GENERATOR_TRIBES, balance_rules, selectable_sigils, sigil_table
from .sigils import conflict_reason


class CardValidationError(ValueError):
    def __init__(self, issues: list[str]):
        super().__init__("; ".join(issues))
        self.issues = issues


@dataclass
class BalanceResult:
    attack: int
    health: int
    sigils: list[str]
    blood_cost: int | None
    card_power: int
    status: str
    adjustments: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _power_of(ability_id: str) -> int:
    entry = selectable_sigils().get(ability_id)
    if entry is None:
        for other in sigil_table()["not_auto_selected"]:
            if other["id"] == ability_id:
                return other["power"]
        return 0
    return entry["power"]


def combo_surcharge(sigils: list[str]) -> tuple[int, list[str]]:
    extra, reasons = 0, []
    for rule in sigil_table()["combo_surcharges"]:
        if set(rule["pair"]) <= set(sigils):
            extra += rule["extra_power"]
            reasons.append(f"+{rule['extra_power']} CP for {'+'.join(rule['pair'])}: {rule['reason']}")
    return extra, reasons


def card_power(attack: int, health: int, sigils: list[str]) -> int:
    weights = balance_rules()["card_power"]
    surcharge, _ = combo_surcharge(sigils)
    return weights["attack_weight"] * attack + weights["health_weight"] * health + sum(map(_power_of, sigils)) + surcharge


def power_breakdown(attack: int, health: int, sigils: list[str]) -> dict[str, Any]:
    weights = balance_rules()["card_power"]
    surcharge, reasons = combo_surcharge(sigils)
    return {
        "formula": "sigil power + health + 2 x attack (+ combo surcharge)",
        "attack_part": weights["attack_weight"] * attack,
        "health_part": weights["health_weight"] * health,
        "sigil_parts": {s: _power_of(s) for s in sigils},
        "combo_surcharge": surcharge,
        "combo_reasons": reasons,
        "total": card_power(attack, health, sigils),
    }


def effective_attack(attack: int, sigils: list[str]) -> int:
    multiplier = 1
    for s in sigils:
        multiplier = max(multiplier, selectable_sigils().get(s, {}).get("strike_multiplier", 1))
    if "TriStrike" in sigils:
        multiplier = max(multiplier, 3)
    return attack * multiplier


def minimum_cost(attack: int, sigils: list[str], tribe: str | None) -> tuple[int, list[str]]:
    rules = balance_rules()
    floor, reasons = (0 if rules["allow_free_cards"] else 1), []
    if tribe and rules["tribe_minimum_cost"].get(tribe, 0) > floor:
        floor = rules["tribe_minimum_cost"][tribe]
        reasons.append(f"{tribe} cards cost at least {floor}")
    by_attack = rules["attack_minimum_cost"].get(str(attack), 0)
    if by_attack > floor:
        floor = by_attack
        reasons.append(f"attack {attack} needs at least {floor} blood (turn-one damage guard)")
    for s in sigils:
        need = selectable_sigils().get(s, {}).get("min_blood", 0)
        if need > floor:
            floor = need
            reasons.append(f"{s} needs at least {need} blood")
    if "Flying" in sigils:
        caps = rules["airborne_attack_cap_by_cost"]
        need = min((int(c) for c, cap in caps.items() if cap >= attack), default=None)
        if need is not None and need > floor:
            floor = need
            reasons.append(f"Airborne with attack {attack} needs at least {need} blood")
    return floor, reasons


def required_blood_cost(attack: int, health: int, sigils: list[str], tribe: str | None = None) -> tuple[int | None, list[str]]:
    """Cheapest legal blood cost, or None if the design is too strong for any allowed cost."""
    rules = balance_rules()
    cp = card_power(attack, health, sigils)
    floor, reasons = minimum_cost(attack, sigils, tribe)
    categories = {selectable_sigils().get(s, {}).get("category") for s in sigils}
    airborne_caps = rules["airborne_attack_cap_by_cost"]
    for band in sorted(rules["blood_cost_bands"], key=lambda b: b["blood"]):
        blood = band["blood"]
        if blood < floor or blood > rules["max_blood_cost"]:
            continue
        if "Flying" in sigils and attack > airborne_caps.get(str(blood), attack):
            continue
        if cp > band["max_power"]:
            continue
        if attack > band.get("max_attack", 99) or len(sigils) > band.get("max_sigils", 99):
            continue
        if categories & set(band.get("forbidden_categories", [])):
            continue
        reasons.append(f"CP {cp} fits the {blood}-blood band (max {band['max_power']})")
        return blood, reasons
    reasons.append(f"CP {cp} exceeds every band up to {rules['max_blood_cost']} blood")
    return None, reasons


def _classify_unknown(ability_id: str) -> str:
    table = sigil_table()
    for group, members in table["excluded"].items():
        if ability_id in members:
            return f"'{ability_id}' is incompatible with Act 1 ({group.replace('_', ' ')})"
    for entry in table["not_auto_selected"]:
        if entry["id"] == ability_id:
            return f"'{ability_id}' ({entry['display_name']}) is not allowed on generated cards: {entry['reason']}"
    return f"'{ability_id}' is not a known Inscryption ability id"


def sigil_errors(sigils: list[str]) -> list[str]:
    """Allowlist, count, duplicate and combination problems in a sigil list."""
    errors: list[str] = []
    limit = balance_rules()["max_sigils"]
    if len(sigils) > limit:
        errors.append(f"{len(sigils)} sigils; generated cards may have at most {limit}")
    if len(set(sigils)) != len(sigils):
        errors.append("duplicate sigils")
    allow = selectable_sigils()
    errors += [_classify_unknown(s) for s in sigils if s not in allow]
    for i, a in enumerate(sigils):
        for b in sigils[i + 1:]:
            why = conflict_reason(a, b)
            if why:
                errors.append(f"{a} + {b}: {why}")
    return errors


def validate_design(design: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a design dict: attack, health, sigils, blood_cost, tribe[, subject_kind]."""
    rules = balance_rules()
    bounds = rules["stat_bounds"]
    errors: list[str] = []
    warnings: list[str] = []
    attack, health = design.get("attack"), design.get("health")
    sigils = list(design.get("sigils", []))
    tribe = design.get("tribe", "Miscellaneous")

    for name, value, lo, hi in (("attack", attack, bounds["attack_min"], bounds["attack_max"]),
                                ("health", health, bounds["health_min"], bounds["health_max"])):
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"{name} must be an integer (got {value!r})")
        elif not lo <= value <= hi:
            errors.append(f"{name} {value} is outside the Act 1 range {lo}-{hi}")
    if tribe not in GENERATOR_TRIBES:
        errors.append(f"tribe '{tribe}' is not one of {GENERATOR_TRIBES}")
    if design.get("subject_kind") and design["subject_kind"] not in {"animal", "colony"} and tribe != "Miscellaneous":
        errors.append(f"a {design['subject_kind']} subject cannot have the {tribe} tribe")
    errors += sigil_errors(sigils)
    if errors:
        return errors, warnings
    allow = selectable_sigils()

    eff = effective_attack(attack, sigils)
    if eff > rules["max_effective_attack"]:
        errors.append(f"effective attack {eff} exceeds {rules['max_effective_attack']} (a turn-one win from an unmodified card)")
    for s in sigils:
        override = allow[s].get("attack_override")
        if override is not None and attack != override:
            errors.append(f"{allow[s]['display_name']} cards use attack {override} (got {attack})")
    required, reasons = required_blood_cost(attack, health, sigils, tribe)
    if required is None:
        errors.append(f"too strong for any cost up to {rules['max_blood_cost']} blood ({reasons[-1]})")
    elif "blood_cost" in design and design["blood_cost"] is not None and design["blood_cost"] != required:
        word = "under-costed" if design["blood_cost"] < required else "over-costed"
        errors.append(f"{word}: blood cost {design['blood_cost']} but CP {card_power(attack, health, sigils)} needs {required}")
    if required is not None:
        observed = vanilla_cp_range(required)
        cp = card_power(attack, health, sigils)
        if observed and not observed[0] <= cp <= observed[1]:
            warnings.append(f"CP {cp} is outside the vanilla range {observed} for {required} blood")
    if "Flying" in sigils and attack == 0:
        warnings.append("Airborne card with 0 attack never deals damage")
    return errors, warnings


def vanilla_cp_range(blood: int) -> tuple[int, int] | None:
    """Lowest and highest Card Power among non-outlier vanilla commons at this blood cost."""
    cards = [c for c in balance_rules()["calibration"]["cards"] if c["blood"] == blood and not c.get("outlier")]
    if not cards:
        return None
    powers = [card_power(c["attack"], c["health"], c["sigils"]) for c in cards]
    return min(powers), max(powers)


def balance_design(attack: int, health: int, sigils: list[str], tribe: str = "Miscellaneous",
                   priorities: dict[str, int] | None = None, protected: set[str] | None = None,
                   subject_kind: str | None = None) -> BalanceResult:
    """Correct a draft into a legal design, recording every change.

    Order: drop disallowed/duplicate sigils -> resolve conflicts -> trim to the sigil
    limit -> apply sigil attack overrides -> clamp stats -> enforce effective attack
    -> while no blood cost fits: cap Airborne attack, drop the lowest-priority
    unprotected sigil, then lower the stat that carries more power.
    """
    rules = balance_rules()
    bounds = rules["stat_bounds"]
    allow = selectable_sigils()
    priorities = priorities or {s: allow.get(s, {}).get("priority", 0) for s in sigils}
    protected = protected or set()
    adjustments: list[str] = []

    kept: list[str] = []
    for s in sigils:
        if s not in allow:
            adjustments.append(f"removed sigil: {_classify_unknown(s)}")
        elif s in kept:
            adjustments.append(f"removed duplicate sigil {s}")
        else:
            kept.append(s)
    kept.sort(key=lambda s: -priorities.get(s, allow[s]["priority"]))
    resolved: list[str] = []
    for s in kept:
        clash = next((conflict_reason(r, s) for r in resolved if conflict_reason(r, s)), None)
        if clash:
            adjustments.append(f"removed {s}: {clash}")
        else:
            resolved.append(s)
    while len(resolved) > rules["max_sigils"]:
        adjustments.append(f"removed {resolved[-1]}: more than {rules['max_sigils']} sigils")
        resolved.pop()

    for s in resolved:
        override = allow[s].get("attack_override")
        if override is not None and attack != override:
            adjustments.append(f"attack {attack} -> {override}: {allow[s]['display_name']} needs only one point of damage")
            attack = override

    clamped_attack = max(bounds["attack_min"], min(bounds["attack_max"], int(attack)))
    clamped_health = max(bounds["health_min"], min(bounds["health_max"], int(health)))
    if (clamped_attack, clamped_health) != (attack, health):
        adjustments.append(f"stats {attack}/{health} clamped to {clamped_attack}/{clamped_health}")
    attack, health = clamped_attack, clamped_health

    while effective_attack(attack, resolved) > rules["max_effective_attack"] and attack > 0:
        attack -= 1
        adjustments.append(f"attack lowered to {attack}: effective attack must stay <= {rules['max_effective_attack']}")

    max_cost = rules["max_blood_cost"]
    for _ in range(40):
        cost, _reasons = required_blood_cost(attack, health, resolved, tribe)
        if cost is not None:
            break
        cap = rules["airborne_attack_cap_by_cost"].get(str(max_cost), attack)
        droppable = [s for s in resolved if s not in protected]
        if "Flying" in resolved and attack > cap:
            adjustments.append(f"attack {attack} -> {cap}: Airborne cap at {max_cost} blood")
            attack = cap
        elif len(resolved) > 1 and droppable:
            victim = min(droppable, key=lambda s: priorities.get(s, allow[s]["priority"]))
            resolved.remove(victim)
            adjustments.append(f"removed {victim}: card too strong for {max_cost} blood")
        elif health > bounds["health_min"] and (health >= 2 * attack or attack == 0):
            health -= 1
            adjustments.append(f"health lowered to {health}: card too strong for {max_cost} blood")
        elif attack > bounds["attack_min"]:
            attack -= 1
            adjustments.append(f"attack lowered to {attack}: card too strong for {max_cost} blood")
        else:
            break

    design = {"attack": attack, "health": health, "sigils": resolved, "tribe": tribe}
    if subject_kind:
        design["subject_kind"] = subject_kind
    cost, _ = required_blood_cost(attack, health, resolved, tribe)
    design["blood_cost"] = cost
    errors, warnings = validate_design(design)
    status = "rejected" if errors or cost is None else ("adjusted" if adjustments else "valid")
    return BalanceResult(attack, health, resolved, cost, card_power(attack, health, resolved), status,
                         adjustments, errors, warnings)


def assert_valid(design: dict[str, Any]) -> None:
    """Strict check used by the exporter and by callers that must not auto-correct."""
    errors, _ = validate_design(design)
    if errors:
        raise CardValidationError(errors)
