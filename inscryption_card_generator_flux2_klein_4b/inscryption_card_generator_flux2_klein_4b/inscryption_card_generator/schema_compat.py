"""Compatibility layer for your existing ObjectAnalysis schema.

If a path to the original Inscryption-AI project is supplied, this module can
import the user's exact `schemas.py`. Otherwise it falls back to an identical
local copy so the add-on can still run standalone.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

Material = Literal[
    "metal", "wood", "glass", "plastic", "fabric", "rubber", "stone",
    "ceramic", "paper", "leather", "organic", "electronic", "mixed", "unknown"
]
Texture = Literal[
    "smooth", "rough", "fuzzy", "woven", "glossy", "matte", "sharp",
    "soft", "ridged", "segmented", "irregular"
]
Hardness = Literal["soft", "medium", "hard"]
Flexibility = Literal["rigid", "semi_flexible", "flexible"]
Size = Literal["tiny", "small", "medium", "large"]
Shape = Literal["round", "cylindrical", "flat", "angular", "elongated", "boxy", "irregular"]
Confidence = Literal["low", "medium", "high"]
Feature = Literal[
    "fur", "feathers", "scales", "skin", "shell", "carapace", "wings", "beak", "claws",
    "talons", "fangs", "horns", "antlers", "tusks", "hooves", "tail", "fins", "quills",
    "spines", "thorns", "stinger", "pincers", "mandibles", "antennae", "many_legs",
    "leaves", "bark", "petals", "seeds", "blade", "point"
]


class LocalObjectAnalysis(BaseModel):
    object_name: str
    dominant_material: Material
    secondary_materials: list[Material]
    textures: list[Texture]
    hardness: Hardness
    flexibility: Flexibility
    size: Size
    shape: Shape
    reflective: bool
    sharp: bool
    organic: bool
    electronic: bool
    confidence: Confidence
    # Optional extensions (absent in older scans; defaults keep them backward compatible).
    visible_features: list[Feature] = []
    subject_count: int = 1


def load_external_schema(project_root: Path | None):
    if project_root is None:
        return LocalObjectAnalysis
    schema_path = project_root / "schemas.py"
    if not schema_path.exists():
        return LocalObjectAnalysis
    spec = importlib.util.spec_from_file_location("user_schemas", schema_path)
    if spec is None or spec.loader is None:
        return LocalObjectAnalysis
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("user_schemas", mod)
    spec.loader.exec_module(mod)
    return getattr(mod, "ObjectAnalysis", LocalObjectAnalysis)


def parse_analysis(json_text: str, project_root: Path | None = None):
    Schema = load_external_schema(project_root)
    return Schema.model_validate_json(json_text)
