"""JSON parsing, validation and normalization of the analyzer output."""
import json

import pytest

from conftest import PINECONE, REPO_ROOT, scan
from inscryption_card_generator.analysis import AnalysisValidationError, normalize_analysis
from inscryption_card_generator.schema_compat import load_external_schema, parse_analysis


def test_pinecone_parses_without_issues():
    a = normalize_analysis(PINECONE)
    assert a.object_name == "pinecone"
    assert a.dominant_material == "organic" and a.secondary_materials == ["wood"]
    assert a.textures == ["rough", "ridged", "sharp"]
    assert (a.hardness, a.flexibility, a.size, a.shape) == ("hard", "rigid", "small", "irregular")
    assert (a.reflective, a.sharp, a.organic, a.electronic) == (False, True, True, False)
    assert a.issues == [] and a.contradictions == [] and a.missing == []
    assert a.effective_confidence == "high"


def test_text_with_markdown_fences_and_prose_is_accepted():
    text = "Here you go:\n```json\n" + json.dumps(PINECONE) + "\n```"
    assert normalize_analysis(text).object_name == "pinecone"


def test_pydantic_model_input_from_original_schema():
    model = parse_analysis(json.dumps(PINECONE))
    assert normalize_analysis(model).sharp is True


def test_synonyms_are_mapped_and_unknown_values_dropped():
    a = normalize_analysis(scan("dog", textures=["Spiky", "feathery", "sparkly"], hardness="Very Hard",
                                flexibility="semi-flexible", size="Huge", shape="spherical", dominant_material="steel"))
    assert a.textures == ["sharp", "fuzzy"]
    assert (a.hardness, a.flexibility, a.size, a.shape, a.dominant_material) == ("hard", "semi_flexible", "large", "round", "metal")
    assert any(i.code == "invalid_value" and "sparkly" in i.message for i in a.issues)


def test_missing_booleans_are_unknown_not_false():
    data = scan("dog")
    del data["sharp"], data["organic"]
    a = normalize_analysis(data)
    assert a.sharp is None and a.organic is None
    assert {"sharp", "organic"} <= set(a.missing)


def test_explicit_false_stays_false_and_string_booleans_parse():
    a = normalize_analysis(scan("dog", sharp=False, reflective="yes", electronic="false"))
    assert a.sharp is False and a.reflective is True and a.electronic is False
    assert "sharp" not in a.missing


def test_missing_or_numeric_confidence():
    data = scan("dog")
    del data["confidence"]
    assert normalize_analysis(data).effective_confidence == "low"
    assert normalize_analysis(scan("dog", confidence=0.9)).confidence == "high"
    assert normalize_analysis(scan("dog", confidence=55)).confidence == "medium"


def test_contradictions_are_recorded_and_lower_confidence():
    a = normalize_analysis(scan("turtle", organic=False, dominant_material="organic", hardness="hard",
                                flexibility="flexible", textures=["smooth", "rough", "sharp"], sharp=False))
    assert a.organic is True  # dominant_material=organic wins over the flag
    assert len(a.contradictions) == 4
    assert a.confidence == "high" and a.effective_confidence == "low"


def test_many_missing_fields_lower_confidence():
    a = normalize_analysis({"object_name": "raven", "confidence": "high"})
    assert a.effective_confidence == "medium"
    assert a.dominant_material == "unknown" and a.size is None


def test_generic_name_forces_low_confidence():
    assert normalize_analysis(scan("object")).effective_confidence == "low"


@pytest.mark.parametrize("bad", ["not json at all", "[1, 2]", json.dumps({"dominant_material": "wood"}),
                                 json.dumps({"object_name": "   "}), 42])
def test_unusable_inputs_raise(bad):
    with pytest.raises(AnalysisValidationError):
        normalize_analysis(bad)


def test_optional_extension_fields_are_backward_compatible():
    # The original scanner schema (repo root schemas.py) still accepts JSON without the new fields...
    schema = load_external_schema(REPO_ROOT)
    model = schema.model_validate(PINECONE)
    assert model.visible_features == [] and model.subject_count == 1
    # ...and accepts them when present.
    assert schema.model_validate(dict(PINECONE, visible_features=["seeds"], subject_count=2)).subject_count == 2
    a = normalize_analysis(dict(PINECONE, visible_features=["Thorns", "wings", "glitter"]))
    assert a.visible_features == ["thorns", "wings"]
