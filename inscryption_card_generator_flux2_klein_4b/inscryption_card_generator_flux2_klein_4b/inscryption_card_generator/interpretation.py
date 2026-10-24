"""Stage 6: interpret the image JSON's physical properties in the context of the subject.

The JSON describes what the camera saw, not gameplay. This module turns it into a
small set of named pieces of evidence, each with the fields that support it:

* toughness       - hardness, dominant and secondary material describe the SAME
                    rigidity, so only the strongest of them counts (no stacking).
* natural_weapon  - an animal whose identity has claws/fangs/horns/... AND whose
                    image shows sharpness or the weapon. Never for non-animals.
* predator        - an animal identified as a predator that is at least medium sized.
* protective      - shell/carapace/thick hide in the identity, corroborated by a
                    ridged/segmented/rough/glossy texture or a visible shell. Hardness
                    alone does not count (it is already used for toughness).
* edge            - a rigid, hard, angular/elongated, clearly sharp OBJECT (a blade).
* passive_spines  - a rigid, clearly sharp non-animal that is not blade-shaped
                    (pinecone scales, burrs). Supports Sharp Quills, never attack.
* tall_structure  - a large, rigid, elongated/cylindrical non-animal (Mighty Leap).
* stone_body      - a stone object or mineral (Made of Stone).
* brittle         - rigid glass or ceramic.

reflective, organic and electronic never change stats directly; they are
recorded as descriptive evidence and used by identification.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .analysis import NormalizedAnalysis
from .config import balance_rules, size_rank, taxonomy_table
from .taxonomy import Identification

WEAPON_FEATURES = {"claws", "talons", "fangs", "horns", "antlers", "tusks", "stinger", "pincers", "mandibles"}
SPINE_FEATURES = {"spines", "thorns", "quills", "point", "blade"}
PROTECTIVE_FEATURES = {"shell", "carapace", "scales"}
NON_ANIMAL_KINDS = {"object", "mineral", "remains", "plant", "food", "depiction", "unknown"}


@dataclass
class PhysicalProfile:
    size: str
    toughness_level: int
    toughness_sources: list[str]
    brittle: bool
    sharp_evidence: str
    natural_weapon: bool
    weapons: list[str]
    predator: bool
    protective_structure: bool
    edge: bool
    passive_spines: bool
    tall_structure: bool
    stone_body: bool
    interpretation: dict[str, str] = field(default_factory=dict)

    def rule(self, name: str) -> bool:
        return bool(getattr(self, name, False))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sharp_evidence(a: NormalizedAnalysis) -> str:
    votes = int(a.sharp is True) + int("sharp" in a.textures)
    if votes == 2 or (votes == 1 and set(a.visible_features) & (SPINE_FEATURES | WEAPON_FEATURES)):
        return "strong"
    return "weak" if votes == 1 else "none"


def interpret(a: NormalizedAnalysis, ident: Identification) -> PhysicalProfile:
    rules = balance_rules()
    hm, am = rules["health_model"], rules["attack_model"]
    weapon_traits = set(taxonomy_table()["weapon_traits"])
    protective_traits = set(taxonomy_table()["protective_traits"])
    notes: dict[str, str] = {}
    traits = set(ident.traits)
    features = set(a.visible_features)
    animal = ident.is_animal and ident.kind == "animal"

    size = a.size or "small"
    baseline = f"health {hm['size_base'][size]}" + (f", attack {am['animal_size_base'][size]}" if animal else "")
    notes["size"] = (f"{a.size}: sets the baseline ({baseline}); never sets cost by itself" if a.size
                     else f"missing: assumed 'small' (conservative baseline: {baseline})")

    # Toughness: one shared level from overlapping evidence.
    candidates = []
    if a.hardness:
        candidates.append((hm["hardness_level"][a.hardness], f"hardness={a.hardness}"))
    candidates.append((hm["material_level"].get(a.dominant_material, 0), f"dominant_material={a.dominant_material}"))
    for mat in a.secondary_materials:
        level = hm["material_level"].get(mat, 0) - hm["secondary_material_discount"]
        candidates.append((max(0, level), f"secondary_material={mat}"))
    level = min(2, max(c[0] for c in candidates))
    sources = [label for value, label in candidates if value == level and level > 0]
    notes["hardness"] = (f"{a.hardness}: toughness evidence" if a.hardness else "missing: no toughness evidence")
    notes["dominant_material"] = f"{a.dominant_material}: toughness evidence (overlaps hardness; strongest one wins)"
    notes["secondary_materials"] = (f"{a.secondary_materials}: weaker supplementary toughness evidence"
                                    if a.secondary_materials else "none")
    notes["toughness"] = (f"level {level} from {sources or ['no hard materials']} -> "
                          f"+{hm['toughness_bonus'][str(level)]} health")

    brittle = a.dominant_material in hm["brittle_materials"] and a.flexibility == "rigid"
    notes["flexibility"] = (f"{a.flexibility}: secondary; " if a.flexibility else "missing; ") + (
        "rigid brittle material -> -1 health" if brittle else "no direct stat effect")

    sharp_evidence = _sharp_evidence(a)
    notes["sharp"] = f"{a.sharp}: sharpness evidence is {sharp_evidence}"

    weapons = sorted(traits & weapon_traits)
    natural_weapon = animal and bool(weapons) and (sharp_evidence != "none" or bool(features & WEAPON_FEATURES))
    if animal and weapons:
        notes["natural_weapon"] = (f"{weapons} corroborated by the image -> +1 attack" if natural_weapon
                                   else f"{weapons} known for this animal but not visible/sharp in the scan -> no bonus")
    elif sharp_evidence != "none":
        notes["natural_weapon"] = "sharpness on a non-animal (or an animal without natural weapons) is not a weapon"

    predator = animal and "predator" in traits and size_rank(size) >= size_rank(am["predator_min_size"])

    protective_corroboration = (set(a.textures) & set(hm["protective_corroborating_textures"])) or (features & PROTECTIVE_FEATURES)
    protective = animal and bool(traits & protective_traits) and bool(protective_corroboration)
    if animal and traits & protective_traits:
        notes["protective_structure"] = (f"{sorted(traits & protective_traits)} corroborated by {sorted(protective_corroboration)}"
                                         if protective else "protective structure not corroborated by texture/features")

    non_animal = ident.kind in NON_ANIMAL_KINDS
    firm = a.hardness in {"medium", "hard"} and a.flexibility != "flexible"
    edge = (non_animal and ident.kind not in {"plant", "food"} and sharp_evidence == "strong" and firm
            and a.shape in am["object_edge_shapes"])
    passive_spines = non_animal and not edge and sharp_evidence == "strong" and firm and ident.kind != "food"
    tall = (non_animal and size == "large" and a.shape in {"elongated", "cylindrical"}
            and a.flexibility in {"rigid", "semi_flexible"})
    stone_body = ident.kind in {"mineral", "object"} and a.dominant_material == "stone"
    if edge:
        notes["edge"] = "rigid, hard, sharp and blade-shaped object -> +1 attack (objects are capped at 1)"
    if passive_spines:
        notes["passive_spines"] = "rigid sharp surface on a non-animal -> eligible for Sharp Quills, no attack bonus"

    notes["textures"] = f"{a.textures}: used only as corroboration (sharpness, protective structure), never alone"
    notes["shape"] = f"{a.shape}: only matters for blade-like objects and tall structures"
    notes["reflective"] = f"{a.reflective}: descriptive surface evidence only; no stat effect"
    notes["organic"] = f"{a.organic}: used to tell living subjects from objects and depictions"
    notes["electronic"] = (f"{a.electronic}: electronic subjects become plain object cards; "
                           "Act 1 has no energy or technology sigils")
    notes["confidence"] = f"{a.confidence} reported, {a.effective_confidence} after checks"

    return PhysicalProfile(size=size, toughness_level=level, toughness_sources=sources, brittle=brittle,
                           sharp_evidence=sharp_evidence, natural_weapon=natural_weapon, weapons=weapons,
                           predator=predator, protective_structure=protective, edge=edge,
                           passive_spines=passive_spines, tall_structure=tall, stone_body=stone_body,
                           interpretation=notes)
