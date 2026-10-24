"""Stages 13-14: convert a GeneratedCard into files the game can load.

Primary target: the companion BepInEx plugin ``ScannedCardsLoader`` (C#, in
/inscryption_mod). At game start it reads every ``cards/*.json`` written here and
registers it with InscryptionAPI:

    CardManager.New(modPrefix, card_id, display_name, attack, health, description)
        .SetBloodCost(blood_cost)
        .SetDefaultPart1Card()            // ChoiceNode + TraderOffer, Nature temple
        .AddAbilities(<Ability enum>)     // e.g. Ability.Sharp
        .AddTribes(<Tribe enum>)          // omitted for Miscellaneous (no tribe)
        .SetPortrait(<abs path to 114x94 PNG>)

Optional target: a JSONLoader ``.jldr2`` file (MADH95Mods/JSONCardLoader) for
players who prefer not to install the companion plugin. Use ONE of the two, or
the card is registered twice.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from .artwork import check_act1_portrait
from .balance import CardValidationError, assert_valid
from .card_models import GeneratedCard

MOD_PREFIX = "ScannedCards"
PLUGIN_FOLDER = "ScannedCardsLoader"
SCHEMA_VERSION = 1


class DuplicateCardIdError(ValueError):
    pass


def card_to_mod_json(card: GeneratedCard) -> dict[str, Any]:
    """Flat JSON read by ScannedCardsLoader (Unity JsonUtility: public fields, no nesting)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "card_id": card.card_id,
        "display_name": card.display_name,
        "description": card.description,
        "attack": card.attack,
        "health": card.health,
        "blood_cost": card.blood_cost,
        "tribes": list(card.game_tribes),
        "abilities": card.sigil_ids,
        "portrait": f"{card.card_id}.png",
        "tribe_label": card.tribe,
        "card_power": card.card_power.get("total", 0),
        "validation_status": card.validation_status,
    }


def _check_exportable(card: GeneratedCard) -> None:
    if not card.exportable:
        raise CardValidationError([f"card {card.card_id} is {card.validation_status}; it cannot be exported"]
                                  + card.validation.get("errors", []))
    assert_valid({"attack": card.attack, "health": card.health, "sigils": card.sigil_ids, "tribe": card.tribe,
                  "blood_cost": card.blood_cost, "subject_kind": card.subject_kind})


def find_duplicate_ids(cards: Iterable[GeneratedCard]) -> list[str]:
    seen: set[str] = set()
    dupes: list[str] = []
    for card in cards:
        if card.card_id in seen and card.card_id not in dupes:
            dupes.append(card.card_id)
        seen.add(card.card_id)
    return dupes


def export_card(card: GeneratedCard, portrait: Path, cards_dir: Path, overwrite: bool = False) -> dict[str, str]:
    """Write <card_id>.json and <card_id>.png into the plugin's cards folder."""
    _check_exportable(card)
    problems = check_act1_portrait(portrait)
    if problems:
        raise CardValidationError(problems)

    cards_dir.mkdir(parents=True, exist_ok=True)
    json_path = cards_dir / f"{card.card_id}.json"
    png_path = cards_dir / f"{card.card_id}.png"
    payload = card_to_mod_json(card)
    if json_path.exists():
        existing = json.loads(json_path.read_text(encoding="utf-8"))
        if existing != payload and not overwrite:
            raise DuplicateCardIdError(
                f"{json_path.name} already exists with different content; pass overwrite=True (--overwrite) to replace it")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if portrait.resolve() != png_path.resolve():
        shutil.copyfile(portrait, png_path)
    return {"card_json": str(json_path.resolve()), "portrait": str(png_path.resolve())}


def export_jsonloader(card: GeneratedCard, portrait: Path, out_dir: Path) -> dict[str, str]:
    """Alternative: a JSONLoader card file (fields per the JSONCardLoader docs)."""
    _check_exportable(card)
    out_dir.mkdir(parents=True, exist_ok=True)
    texture = f"{card.card_id}_jl.png"  # distinct file name: JSONLoader searches the plugins folder by name
    data = {
        "name": card.card_id,
        "modPrefix": MOD_PREFIX,
        "displayedName": card.display_name,
        "description": card.description,
        "metaCategories": ["ChoiceNode", "TraderOffer"],
        "cardComplexity": "Simple",
        "temple": "Nature",
        "baseAttack": card.attack,
        "baseHealth": card.health,
        "bloodCost": card.blood_cost,
        "tribes": list(card.game_tribes),
        "abilities": card.sigil_ids,
        "texture": texture,
    }
    path = out_dir / f"{card.card_id}.jldr2"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    shutil.copyfile(portrait, out_dir / texture)
    return {"jldr2": str(path.resolve()), "texture": str((out_dir / texture).resolve())}


def registration_snippet(card: GeneratedCard) -> str:
    """C# equivalent of what ScannedCardsLoader does for this card (for review/debugging)."""
    def lit(text: str) -> str:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'

    lines = [
        f"// Registered at runtime by {PLUGIN_FOLDER} (Plugin.Register) from cards/{card.card_id}.json",
        f"CardInfo info = CardManager.New({lit(MOD_PREFIX)}, {lit(card.card_id)}, {lit(card.display_name)}, "
        f"{card.attack}, {card.health}, {lit(card.description)});",
        f"info.SetBloodCost({card.blood_cost});",
        "info.SetDefaultPart1Card();  // ChoiceNode + TraderOffer, CardTemple.Nature",
    ]
    if card.sigil_ids:
        lines.append("info.AddAbilities(" + ", ".join(f"Ability.{s}" for s in card.sigil_ids) + ");")
    else:
        lines.append("// no sigils")
    if card.game_tribes:
        lines.append("info.AddTribes(" + ", ".join(f"Tribe.{t}" for t in card.game_tribes) + ");")
    else:
        lines.append("// Miscellaneous: no tribe (empty CardInfo.tribes), as for vanilla Cat/Grizzly/Porcupine")
    lines.append(f"info.SetPortrait(TextureHelper.GetImageAsTexture(Path.Combine(cardsDir, {lit(card.card_id + '.png')})));  // 114x94")
    lines.append(f"// in-game card name: {MOD_PREFIX}_{card.card_id}")
    return "\n".join(lines)
