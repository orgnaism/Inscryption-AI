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


# Optional extension: anatomical / structural features actually visible in the photo.
# Lets the card generator tell real claws or shells apart from a generically
# "sharp" or "hard" object. Older scans without it still validate.
Feature = Literal[
    "fur",
    "feathers",
    "scales",
    "skin",
    "shell",
    "carapace",
    "wings",
    "beak",
    "claws",
    "talons",
    "fangs",
    "horns",
    "antlers",
    "tusks",
    "hooves",
    "tail",
    "fins",
    "quills",
    "spines",
    "thorns",
    "stinger",
    "pincers",
    "mandibles",
    "antennae",
    "many_legs",
    "leaves",
    "bark",
    "petals",
    "seeds",
    "blade",
    "point"
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

    # Optional extensions (defaults keep older JSON valid).
    visible_features: list[Feature] = []
    subject_count: int = 1