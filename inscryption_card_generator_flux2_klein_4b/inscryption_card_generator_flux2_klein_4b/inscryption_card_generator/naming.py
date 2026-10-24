"""Stage 7: player-facing card name and description.

Act 1 commons are named after real animals (the guide prefers less common names:
"Lammergeier", "Rattler", "River Snapper"), so names come from the taxonomy entry
or the cleaned object name - not invented fantasy compounds. The description is
the line Leshy reads when the card is first seen; diagnostics stay out of it.
"""
from __future__ import annotations

import hashlib
import json
import re

from .interpretation import PhysicalProfile
from .taxonomy import Identification

SIGIL_LINES = {
    "Flying": "It soars past every defense.", "Submerge": "It slips beneath the water.",
    "Reach": "Nothing flies over it.", "Strafe": "It never stays still.",
    "StrafePush": "It shoves all before it.", "StrafeSwap": "It tramples through the line.",
    "WhackAMole": "It tunnels to wherever it is needed.", "GuardDog": "It guards what is yours.",
    "TailOnHit": "It leaves its tail behind.", "Sharp": "Strike it and bleed.",
    "DebuffEnemy": "Its stench saps the strength of foes.", "MadeOfStone": "Poison and stench do not move it.",
    "DeathShield": "Its first wound never lands.", "Deathtouch": "One bite is enough.",
    "DoubleStrike": "It strikes twice before you blink.", "SplitStrike": "It strikes left and right.",
    "BoneDigger": "It digs up bones.", "OpponentBones": "It profits from every death.",
    "CorpseEater": "It feeds on the fallen.", "QuadrupleBones": "Its bones are worth a fortune.",
    "TripleBlood": "A worthy sacrifice.", "GainAttackOnKill": "Each kill feeds its hunger.",
    "BuffNeighbours": "Others fight harder beside it.", "Tutor": "It finds what you seek.",
    "DrawCopy": "Where there is one, there are more.", "DrawCopyOnDeath": "It will not stay dead.",
    "Sacrificial": "It has lives to spare.", "BeesOnHit": "Disturb it at your peril.",
    "DrawAnt": "The colony sends another.", "DrawRabbits": "Something always crawls out of it.",
    "CreateDams": "It walls off the lanes.", "CreateBells": "Its ringing summons chimes.",
    "Evolve": "Give it time to grow.", "CreateEgg": "It leaves its egg in another's nest.",
    "Morsel": "A meal for a greater beast.", "BuffEnemy": "It only enrages the enemy.",
}
TRIBE_LINES = {
    "Avian": "It watches from above.", "Canine": "It hunts with teeth bared.",
    "Insect": "It skitters in the dark.", "Hooved": "It stamps and snorts.",
    "Reptile": "It waits, cold and patient.", "Miscellaneous": "It does not belong to any tribe.",
}


def choose_display_name(ident: Identification, variant: int = 0) -> str:
    names = ident.names or ["Odd Curio"]
    return names[variant % len(names)][:16].strip()


def physical_line(profile: PhysicalProfile) -> str:
    if profile.edge:
        return "Its edge is keen."
    if profile.passive_spines:
        return "Its scales bristle against any who strike it."
    if profile.brittle:
        return "It looks ready to shatter."
    if profile.toughness_level >= 2:
        return "It is hard and unyielding."
    return "It is small and unremarkable."


def build_description(name: str, ident: Identification, tribe: str, sigil_ids: list[str],
                      profile: PhysicalProfile) -> str:
    first = next((SIGIL_LINES[s] for s in sigil_ids if s in SIGIL_LINES and s != "Flying"), None)
    if first is None and "Flying" in sigil_ids:
        first = SIGIL_LINES["Flying"]
    if ident.kind == "animal":
        line = first or TRIBE_LINES.get(tribe, TRIBE_LINES["Miscellaneous"])
        text = f"The {name}. {line}"
    elif ident.kind == "colony":
        text = f"The {name}. {first or 'Something lives inside.'}"
    elif ident.kind == "depiction":
        text = f"A {name.lower()}. A mere likeness of a living thing."
    else:
        text = f"A {name.lower()} from beyond the cabin. {first or physical_line(profile)}"
    return text[:120]


def make_card_id(display_name: str, source_attributes: dict, variant: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", display_name.lower()).strip("_") or "card"
    digest = hashlib.sha1((json.dumps(source_attributes, sort_keys=True, default=str) + f"|{variant}").encode()).hexdigest()[:8]
    return f"{slug[:40]}_{digest}"
