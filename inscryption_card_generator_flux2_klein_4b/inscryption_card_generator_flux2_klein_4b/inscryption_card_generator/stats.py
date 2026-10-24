"""Stage 6b: estimate attack and health from the interpreted physical profile.

Every point is traced back to the JSON field (or identity fact) that caused it,
so tests and the diagnostics can show that no single attribute dominates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .config import balance_rules, size_rank
from .interpretation import PhysicalProfile
from .taxonomy import Identification


@dataclass
class StatEstimate:
    attack: int
    health: int
    trace: list[str] = field(default_factory=list)
    # Card Power added by each JSON field on top of the size baseline (attack points count double).
    bonus_power_by_field: dict[str, int] = field(default_factory=dict)
    protective_bonus_applied: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _add(est: StatEstimate, field_name: str, power: int) -> None:
    est.bonus_power_by_field[field_name] = est.bonus_power_by_field.get(field_name, 0) + power


def estimate_stats(ident: Identification, profile: PhysicalProfile, tribe: str, confidence: str) -> StatEstimate:
    rules = balance_rules()
    am, hm, bounds = rules["attack_model"], rules["health_model"], rules["stat_bounds"]
    est = StatEstimate(attack=0, health=hm["size_base"][profile.size])
    est.trace.append(f"health {est.health} from size={profile.size}")

    # ---- attack
    if ident.kind == "animal":
        est.attack = am["animal_size_base"][profile.size]
        est.trace.append(f"attack {est.attack} from size={profile.size} (animal baseline)")
        if profile.natural_weapon:
            est.attack += am["corroborated_weapon_bonus"]
            _add(est, "sharp/visible_features", 2 * am["corroborated_weapon_bonus"])
            est.trace.append(f"+{am['corroborated_weapon_bonus']} attack: natural weapons {profile.weapons} visible in the scan")
        if profile.predator:
            est.attack += am["predator_bonus"]
            _add(est, "object_name(predator)+size", 2 * am["predator_bonus"])
            est.trace.append(f"+{am['predator_bonus']} attack: predator of size {profile.size}")
    elif ident.kind == "colony":
        est.trace.append(f"attack capped at {am['colony_attack_cap']}: colonies defend, they do not hunt")
    else:
        est.trace.append(f"attack 0: {ident.kind} subjects do not hunt")
        if profile.edge:
            est.attack += am["object_edge_bonus"]
            _add(est, "sharp/shape", 2 * am["object_edge_bonus"])
            est.trace.append(f"+{am['object_edge_bonus']} attack: blade-like sharp object")
        if est.attack > am["non_animal_attack_cap"]:
            est.attack = am["non_animal_attack_cap"]
            est.trace.append(f"attack capped at {am['non_animal_attack_cap']} for non-animals")
    if ident.kind == "colony":
        est.attack = min(est.attack, am["colony_attack_cap"])

    # ---- health
    tough = hm["toughness_bonus"][str(profile.toughness_level)]
    if tough:
        est.health += tough
        _add(est, "hardness/material", tough)
        est.trace.append(f"+{tough} health: toughness level {profile.toughness_level} from {profile.toughness_sources}")
    if profile.protective_structure:
        est.health += hm["protective_structure_bonus"]
        est.protective_bonus_applied = True
        _add(est, "textures/visible_features(protective)", hm["protective_structure_bonus"])
        est.trace.append(f"+{hm['protective_structure_bonus']} health: shell/carapace/hide corroborated by the scan")
    if profile.brittle:
        est.health -= hm["brittle_penalty"]
        _add(est, "flexibility+material(brittle)", -hm["brittle_penalty"])
        est.trace.append(f"-{hm['brittle_penalty']} health: rigid brittle material")

    # ---- tribe conventions (calibrated on vanilla tribes; see BALANCING.md)
    shaping = rules["tribe_shaping"].get(tribe, {})
    if "max_attack_if_small" in shaping and size_rank(profile.size) <= size_rank("small") \
            and est.attack > shaping["max_attack_if_small"]:
        est.attack = shaping["max_attack_if_small"]
        est.trace.append(f"{tribe}: small fliers keep attack <= {est.attack}")
    if shaping.get("health_exceeds_attack") and est.attack >= est.health:
        est.attack = max(0, est.health - 1)
        est.trace.append(f"{tribe}: health stays above attack -> attack {est.attack}")
    if "max_health_over_attack" in shaping and est.health > est.attack + shaping["max_health_over_attack"]:
        est.health = est.attack + shaping["max_health_over_attack"]
        est.trace.append(f"{tribe}: hard hitters with modest health -> health {est.health}")
    if "defensive_attack_cap" in shaping and profile.protective_structure and est.attack > shaping["defensive_attack_cap"]:
        est.attack = shaping["defensive_attack_cap"]
        est.trace.append(f"{tribe}: shelled reptiles are defensive -> attack {est.attack}")

    # ---- confidence caps
    conf = rules["confidence"][confidence]
    if "attack_cap" in conf and est.attack > conf["attack_cap"]:
        est.attack = conf["attack_cap"]
        est.trace.append(f"{confidence} confidence: attack capped at {est.attack}")
    if "health_cap" in conf and est.health > conf["health_cap"]:
        est.health = conf["health_cap"]
        est.trace.append(f"{confidence} confidence: health capped at {est.health}")

    est.attack = max(bounds["attack_min"], min(bounds["attack_max"], est.attack))
    est.health = max(bounds["health_min"], min(bounds["health_max"], est.health))
    est.trace.append(f"estimate: {est.attack}/{est.health}")
    return est
