"""Loads the tunable JSON data files (balance rules, sigil allowlist, taxonomy).

All balancing numbers live in ``data/*.json`` so they can be tuned without
touching the image-analysis pipeline. Pass a different directory through
``INSCRYPTION_RULES_DIR`` to experiment with an alternative rule set.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"

SIZE_ORDER = ["tiny", "small", "medium", "large"]
CONFIDENCE_ORDER = ["low", "medium", "high"]
GENERATOR_TRIBES = ["Avian", "Canine", "Insect", "Hooved", "Reptile", "Miscellaneous"]


def _data_dir() -> Path:
    override = os.getenv("INSCRYPTION_RULES_DIR")
    return Path(override) if override else DATA_DIR


@lru_cache(maxsize=None)
def _load(name: str, directory: str) -> dict[str, Any]:
    path = Path(directory) / name
    return json.loads(path.read_text(encoding="utf-8"))


def balance_rules() -> dict[str, Any]:
    return _load("balance_rules.json", str(_data_dir()))


def sigil_table() -> dict[str, Any]:
    return _load("sigils.json", str(_data_dir()))


def taxonomy_table() -> dict[str, Any]:
    return _load("taxonomy.json", str(_data_dir()))


def selectable_sigils() -> dict[str, dict[str, Any]]:
    """Ability enum name -> allowlist entry."""
    return {entry["id"]: entry for entry in sigil_table()["selectable"]}


def all_known_ability_ids() -> set[str]:
    table = sigil_table()
    ids = {e["id"] for e in table["selectable"]}
    ids |= {e["id"] for e in table["not_auto_selected"]}
    for group in table["excluded"].values():
        ids |= set(group)
    return ids


def size_rank(size: str) -> int:
    return SIZE_ORDER.index(size) if size in SIZE_ORDER else 1


def confidence_rank(confidence: str) -> int:
    return CONFIDENCE_ORDER.index(confidence) if confidence in CONFIDENCE_ORDER else 0


def clear_caches() -> None:
    _load.cache_clear()
