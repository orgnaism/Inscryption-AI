"""Legacy entry point kept for backward compatibility.

The original rules picked random 2-4 stats and used sigils/tribes that do not
exist in Inscryption ("Battery Spark", "Bone Heap", "Woodland", "Construct"), so
their cards could not be loaded by the game. ``generate_card_data`` now returns
the same flat CardData shape, produced by the balanced Act 1 generator.
"""
from __future__ import annotations

from .card_models import CardData
from .generator import design_card


def generate_card_data(obj, variant: int = 0) -> CardData:
    card = design_card(obj, variant=variant)
    return CardData(
        name=card.display_name,
        attack=card.attack,
        health=card.health,
        cost_blood=card.cost_blood,
        sigil_name=card.sigil_name,
        sigil_description=" ".join(s["effect"] for s in card.sigils) or "No sigil.",
        tribe=card.tribe,
        rarity="Uncertain" if card.rescan_recommended else "Common",
        lore=card.description,
    )
