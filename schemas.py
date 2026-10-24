from typing import Literal
from pydantic import BaseModel


Material = Literal[
    "metal",
    "wood",
    "glass",
    "plastic",
    "fabric",
    "rubber",
    "stone",
    "ceramic",
    "paper",
    "leather",
    "organic",
    "electronic",
    "mixed",
    "unknown"
]


Texture = Literal[
    "smooth",
    "rough",
    "fuzzy",
    "woven",
    "glossy",
    "matte",
    "sharp",
    "soft",
    "ridged",
    "segmented",
    "irregular"
]


Hardness = Literal[
    "soft",
    "medium",
    "hard"
]


Flexibility = Literal[
    "rigid",
    "semi_flexible",
    "flexible"
]


Size = Literal[
    "tiny",
    "small",
    "medium",
    "large"
]


Shape = Literal[
    "round",
    "cylindrical",
    "flat",
    "angular",
    "elongated",
    "boxy",
    "irregular"
]


Confidence = Literal[
    "low",
    "medium",
    "high"
]


class ObjectAnalysis(BaseModel):
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