from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any


@dataclass
class CardData:
    """Legacy flat card record (kept for code that still imports rules.generate_card_data)."""
    name: str
    attack: int
    health: int
    cost_blood: int
    sigil_name: str
    sigil_description: str
    tribe: str
    rarity: str
    lore: str
    portrait_path: str = ""
    full_card_path: str = ""
    prompt_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GeneratedCard:
    """Internal representation of a generated Act 1 card.

    Player-facing fields (display_name, description, stats, tribe, sigils) are kept
    apart from ``diagnostics``, which records how the image JSON produced them.
    """
    card_id: str
    display_name: str
    description: str
    object_name: str
    subject_kind: str
    tribe: str
    game_tribes: list[str]
    attack: int
    health: int
    blood_cost: int | None
    sigils: list[dict[str, Any]]
    card_power: dict[str, Any]
    source_attributes: dict[str, Any]
    validation_status: str
    validation: dict[str, Any]
    rescan_recommended: bool = False
    variant: int = 0
    artwork_reference: dict[str, str] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def sigil_ids(self) -> list[str]:
        return [s["id"] for s in self.sigils]

    @property
    def exportable(self) -> bool:
        return self.validation_status != "rejected" and self.blood_cost is not None

    # Legacy accessors used by the original renderer/prompt code.
    @property
    def name(self) -> str:
        return self.display_name

    @property
    def cost_blood(self) -> int:
        return self.blood_cost or 0

    @property
    def sigil_name(self) -> str:
        return ", ".join(s["display_name"] for s in self.sigils) or "No sigil"

    @property
    def lore(self) -> str:
        return self.description

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
