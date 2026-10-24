"""Stage 3: parse, validate and normalize the analyzer's ObjectAnalysis JSON.

The strict pydantic schema (``schemas.py`` / ``schema_compat.py``) rejects the
whole scan if a small vision model writes "Spiky" instead of "sharp". This module
keeps the same schema as its vocabulary but is lenient about input: values are
lower-cased, common synonyms are mapped, unknown values are dropped with an
issue, missing fields stay ``None`` (distinct from an explicit ``False``) and
contradictions are recorded and lower the effective confidence.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .config import CONFIDENCE_ORDER, balance_rules

MATERIALS = ["metal", "wood", "glass", "plastic", "fabric", "rubber", "stone", "ceramic",
             "paper", "leather", "organic", "electronic", "mixed", "unknown"]
TEXTURES = ["smooth", "rough", "fuzzy", "woven", "glossy", "matte", "sharp", "soft",
            "ridged", "segmented", "irregular"]
HARDNESS = ["soft", "medium", "hard"]
FLEXIBILITY = ["rigid", "semi_flexible", "flexible"]
SIZES = ["tiny", "small", "medium", "large"]
SHAPES = ["round", "cylindrical", "flat", "angular", "elongated", "boxy", "irregular"]
CONFIDENCES = CONFIDENCE_ORDER
# Optional extension field (backward compatible: absent in old JSON).
FEATURES = ["fur", "feathers", "scales", "skin", "shell", "carapace", "wings", "beak", "claws",
            "talons", "fangs", "horns", "antlers", "tusks", "hooves", "tail", "fins", "quills",
            "spines", "thorns", "stinger", "pincers", "mandibles", "antennae", "many_legs",
            "leaves", "bark", "petals", "seeds", "blade", "point"]

SYNONYMS: dict[str, dict[str, str]] = {
    "material": {
        "rock": "stone", "mineral": "stone", "granite": "stone", "marble": "stone", "concrete": "stone",
        "steel": "metal", "iron": "metal", "aluminum": "metal", "aluminium": "metal", "copper": "metal",
        "brass": "metal", "tin": "metal", "silver": "metal", "gold": "metal", "metallic": "metal",
        "timber": "wood", "wooden": "wood", "bark": "wood",
        "cloth": "fabric", "cotton": "fabric", "wool": "fabric", "textile": "fabric", "felt": "fabric", "plush": "fabric",
        "porcelain": "ceramic", "clay": "ceramic", "terracotta": "ceramic",
        "cardboard": "paper",
        "plant": "organic", "flesh": "organic", "fur": "organic", "feathers": "organic", "feather": "organic",
        "natural": "organic", "biological": "organic", "bone": "organic", "keratin": "organic", "chitin": "organic",
        "silicone": "rubber", "latex": "rubber",
        "crystal": "glass",
        "electronics": "electronic", "circuitry": "electronic",
        "composite": "mixed", "various": "mixed",
    },
    "texture": {
        "spiky": "sharp", "spiked": "sharp", "pointy": "sharp", "pointed": "sharp", "prickly": "sharp", "thorny": "sharp", "spiny": "sharp",
        "bumpy": "rough", "coarse": "rough", "grainy": "rough", "scaly": "rough", "gritty": "rough",
        "furry": "fuzzy", "hairy": "fuzzy", "fluffy": "fuzzy", "feathery": "fuzzy", "feathered": "fuzzy",
        "shiny": "glossy", "reflective": "glossy", "dull": "matte",
        "slick": "smooth", "sleek": "smooth", "polished": "smooth",
        "grooved": "ridged", "ribbed": "ridged", "scaled": "ridged",
        "jointed": "segmented", "banded": "segmented",
        "knitted": "woven", "braided": "woven",
        "squishy": "soft", "spongy": "soft",
        "jagged": "irregular", "uneven": "irregular",
    },
    "hardness": {"firm": "medium", "moderate": "medium", "very hard": "hard", "solid": "hard", "squishy": "soft"},
    "flexibility": {"semi flexible": "semi_flexible", "semi-flexible": "semi_flexible", "somewhat flexible": "semi_flexible",
                    "bendable": "semi_flexible", "stiff": "rigid", "solid": "rigid", "floppy": "flexible",
                    "elastic": "flexible", "pliable": "flexible"},
    "size": {"very small": "tiny", "miniature": "tiny", "minuscule": "tiny", "big": "large", "huge": "large",
             "very large": "large", "mid": "medium", "average": "medium", "moderate": "medium"},
    "shape": {"spherical": "round", "circular": "round", "oval": "round", "ovoid": "round", "long": "elongated",
              "oblong": "elongated", "slender": "elongated", "thin": "elongated", "rectangular": "boxy",
              "square": "boxy", "cubic": "boxy", "tube": "cylindrical", "tubular": "cylindrical",
              "pointed": "angular", "triangular": "angular", "conical": "irregular", "organic": "irregular"},
    "confidence": {"very high": "high", "certain": "high", "very low": "low", "uncertain": "low", "moderate": "medium"},
}

GENERIC_NAMES = {"object", "thing", "item", "unknown", "something", "unclear", "unidentified", "n/a", "none", ""}
CRITICAL_FIELDS = ["dominant_material", "textures", "hardness", "size", "shape"]


class AnalysisValidationError(ValueError):
    """The analysis cannot be used at all (not JSON, not an object, no subject)."""


@dataclass
class Issue:
    code: str
    field: str
    message: str


@dataclass
class NormalizedAnalysis:
    object_name: str
    dominant_material: str
    secondary_materials: list[str]
    textures: list[str]
    hardness: str | None
    flexibility: str | None
    size: str | None
    shape: str | None
    reflective: bool | None
    sharp: bool | None
    organic: bool | None
    electronic: bool | None
    confidence: str
    effective_confidence: str
    visible_features: list[str] = field(default_factory=list)
    subject_count: int = 1
    missing: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from model output that may carry markdown fences or prose."""
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise AnalysisValidationError("Analysis output contains no JSON object") from None
        try:
            value = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as exc:
            raise AnalysisValidationError(f"Analysis output is not valid JSON: {exc}") from None
    if not isinstance(value, dict):
        raise AnalysisValidationError("Analysis JSON must be an object")
    return value


def _key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower().replace("_", " ")).strip()


def _enum(raw: dict, name: str, vocab: list[str], syn_key: str, issues: list[Issue], missing: list[str]) -> str | None:
    if name not in raw or raw[name] is None or (isinstance(raw[name], str) and not raw[name].strip()):
        missing.append(name)
        return None
    value = raw[name]
    if not isinstance(value, str):
        issues.append(Issue("invalid_type", name, f"expected a string, got {type(value).__name__}"))
        return None
    key = _key(value)
    underscored = key.replace(" ", "_")
    if underscored in vocab:
        return underscored
    mapped = SYNONYMS.get(syn_key, {}).get(key) or SYNONYMS.get(syn_key, {}).get(key.replace("-", " "))
    if mapped:
        issues.append(Issue("synonym", name, f"'{value}' read as '{mapped}'"))
        return mapped
    issues.append(Issue("invalid_value", name, f"'{value}' is not one of {vocab}; ignored"))
    return None


def _enum_list(raw: dict, name: str, vocab: list[str], syn_key: str, issues: list[Issue], missing: list[str]) -> list[str]:
    if name not in raw or raw[name] is None:
        missing.append(name)
        return []
    value = raw[name]
    if isinstance(value, str):
        value = [v for v in re.split(r"[,;/]", value) if v.strip()]
    if not isinstance(value, list):
        issues.append(Issue("invalid_type", name, f"expected a list, got {type(value).__name__}"))
        return []
    out: list[str] = []
    for item in value:
        if not isinstance(item, str):
            issues.append(Issue("invalid_type", name, f"ignored non-string entry {item!r}"))
            continue
        key = _key(item)
        candidate = key.replace(" ", "_")
        if candidate not in vocab:
            candidate = SYNONYMS.get(syn_key, {}).get(key)
            if candidate:
                issues.append(Issue("synonym", name, f"'{item}' read as '{candidate}'"))
            elif syn_key == "feature" and key.rstrip("s") in vocab:
                candidate = key.rstrip("s")
        if candidate in vocab:
            if candidate not in out:
                out.append(candidate)
        else:
            issues.append(Issue("invalid_value", name, f"'{item}' is not in the {name} vocabulary; ignored"))
    return out


def _bool(raw: dict, name: str, issues: list[Issue], missing: list[str]) -> bool | None:
    if name not in raw or raw[name] is None:
        missing.append(name)
        return None
    value = raw[name]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str) and _key(value) in {"true", "yes", "y", "1"}:
        return True
    if isinstance(value, str) and _key(value) in {"false", "no", "n", "0"}:
        return False
    issues.append(Issue("invalid_value", name, f"{value!r} is not a boolean; treated as unknown"))
    return None


def _confidence(raw: dict, issues: list[Issue], missing: list[str]) -> str:
    value = raw.get("confidence")
    if value is None:
        missing.append("confidence")
        issues.append(Issue("missing", "confidence", "no confidence reported; assuming low"))
        return "low"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        score = value / 100 if value > 1 else value
        level = "low" if score < 0.4 else "medium" if score < 0.75 else "high"
        issues.append(Issue("synonym", "confidence", f"numeric confidence {value} read as '{level}'"))
        return level
    found = _enum(raw, "confidence", CONFIDENCES, "confidence", issues, [])
    if found is None:
        issues.append(Issue("invalid_value", "confidence", "unreadable confidence; assuming low"))
        return "low"
    return found


def _step_down(level: str, steps: int) -> str:
    index = max(0, CONFIDENCE_ORDER.index(level) - steps)
    return CONFIDENCE_ORDER[index]


def _find_contradictions(a: NormalizedAnalysis) -> list[str]:
    found: list[str] = []
    living_materials = {"organic", "wood", "leather"}
    inert_materials = {"metal", "glass", "plastic", "electronic", "stone", "ceramic", "rubber"}

    if a.organic is False and a.dominant_material == "organic":
        found.append("organic=false but dominant_material=organic; using organic=true (material is more specific)")
        a.organic = True
    if a.organic is True and a.dominant_material in inert_materials and not (set(a.secondary_materials) & living_materials):
        found.append(f"organic=true but the only materials reported are inert ({a.dominant_material})")
    if a.electronic is False and a.dominant_material == "electronic":
        found.append("electronic=false but dominant_material=electronic; using electronic=true")
        a.electronic = True
    if a.electronic is True and a.dominant_material in living_materials | {"stone", "fabric", "paper"} \
            and "electronic" not in a.secondary_materials:
        found.append(f"electronic=true but no electronic material reported (dominant={a.dominant_material})")
    if a.sharp is False and "sharp" in a.textures:
        found.append("sharp=false but textures include 'sharp'; sharpness treated as weak evidence")
    if a.hardness == "hard" and a.flexibility == "flexible":
        found.append("hardness=hard with flexibility=flexible; flexibility ignored")
    if a.hardness == "hard" and "soft" in a.textures:
        found.append("hardness=hard but textures include 'soft'")
    if "smooth" in a.textures and "rough" in a.textures:
        found.append("textures include both 'smooth' and 'rough'")
    return found


def normalize_analysis(source: Any) -> NormalizedAnalysis:
    """Turn analyzer output (JSON text, dict, or pydantic model) into a NormalizedAnalysis."""
    if hasattr(source, "model_dump"):
        raw = source.model_dump()
    elif isinstance(source, (bytes, bytearray)):
        raw = extract_json_object(source.decode("utf-8", errors="replace"))
    elif isinstance(source, str):
        raw = extract_json_object(source)
    elif isinstance(source, dict):
        raw = dict(source)
    else:
        raise AnalysisValidationError(f"Unsupported analysis input type: {type(source).__name__}")

    name = raw.get("object_name")
    if not isinstance(name, str) or not name.strip():
        raise AnalysisValidationError("Analysis has no object_name; the subject cannot be identified (rescan needed)")

    issues: list[Issue] = []
    missing: list[str] = []
    dominant = _enum(raw, "dominant_material", MATERIALS, "material", issues, missing) or "unknown"
    secondary = [m for m in _enum_list(raw, "secondary_materials", MATERIALS, "material", issues, missing) if m != dominant]

    try:
        subject_count = int(raw.get("subject_count", 1) or 1)
    except (TypeError, ValueError):
        issues.append(Issue("invalid_value", "subject_count", f"{raw.get('subject_count')!r} is not a number; using 1"))
        subject_count = 1

    analysis = NormalizedAnalysis(
        object_name=re.sub(r"\s+", " ", name.strip()),
        dominant_material=dominant,
        secondary_materials=secondary,
        textures=_enum_list(raw, "textures", TEXTURES, "texture", issues, missing),
        hardness=_enum(raw, "hardness", HARDNESS, "hardness", issues, missing),
        flexibility=_enum(raw, "flexibility", FLEXIBILITY, "flexibility", issues, missing),
        size=_enum(raw, "size", SIZES, "size", issues, missing),
        shape=_enum(raw, "shape", SHAPES, "shape", issues, missing),
        reflective=_bool(raw, "reflective", issues, missing),
        sharp=_bool(raw, "sharp", issues, missing),
        organic=_bool(raw, "organic", issues, missing),
        electronic=_bool(raw, "electronic", issues, missing),
        confidence=_confidence(raw, issues, missing),
        effective_confidence="low",
        visible_features=_enum_list(raw, "visible_features", FEATURES, "feature", issues, []) if "visible_features" in raw else [],
        subject_count=max(1, subject_count),
        missing=missing,
        issues=issues,
        raw=raw,
    )
    for name_ in missing:
        if name_ != "confidence":
            issues.append(Issue("missing", name_, "field missing; treated as unknown (not as false)"))

    analysis.contradictions = _find_contradictions(analysis)
    rules = balance_rules()
    steps = len(analysis.contradictions) // max(1, rules["contradictions_per_confidence_step"])
    if sum(1 for f in CRITICAL_FIELDS if f in missing) >= 3:
        steps += 1
        issues.append(Issue("degraded", "confidence", "three or more physical fields missing; confidence lowered"))
    effective = _step_down(analysis.confidence, steps)
    if _key(analysis.object_name) in GENERIC_NAMES:
        effective = "low"
        issues.append(Issue("degraded", "object_name", "generic object_name; confidence set to low"))
    analysis.effective_confidence = effective
    return analysis
