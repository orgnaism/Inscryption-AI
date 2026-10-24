from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class CardData:
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
