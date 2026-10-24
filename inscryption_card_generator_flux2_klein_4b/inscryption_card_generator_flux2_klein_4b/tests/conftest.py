from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]          # generator project
REPO_ROOT = ROOT.parents[1]                         # scanner project (camera.py, analyzer.py, schemas.py)
sys.path.insert(0, str(ROOT))

PINECONE = json.loads((ROOT / "examples" / "pinecone.json").read_text(encoding="utf-8"))

# A neutral living-animal scan; tests override only what they are about.
ANIMAL_BASE = {
    "object_name": "animal",
    "dominant_material": "organic",
    "secondary_materials": [],
    "textures": ["smooth"],
    "hardness": "soft",
    "flexibility": "semi_flexible",
    "size": "small",
    "shape": "irregular",
    "reflective": False,
    "sharp": False,
    "organic": True,
    "electronic": False,
    "confidence": "high",
}

OBJECT_BASE = dict(ANIMAL_BASE, dominant_material="plastic", organic=False, hardness="hard", flexibility="rigid")


def scan(name: str, base: dict | None = None, **overrides) -> dict:
    data = dict(base or ANIMAL_BASE)
    data["object_name"] = name
    data.update(overrides)
    return data


@pytest.fixture
def pinecone() -> dict:
    return dict(PINECONE)
