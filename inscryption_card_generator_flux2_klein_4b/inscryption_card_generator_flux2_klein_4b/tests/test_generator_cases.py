"""The ten required inputs, end to end through the design engine (no artwork model)."""
import json

import pytest

from conftest import PINECONE, scan
from inscryption_card_generator.analysis import normalize_analysis
from inscryption_card_generator.balance import CardValidationError, validate_design
from inscryption_card_generator.generator import design_card
from inscryption_card_generator.prompts import make_portrait_prompt

ANIMAL_WORDS = ("claw", "fang", "teeth", "tooth", "bite", "talon", "predator", "hunt", "beak", "wing")


def assert_playable(card):
    assert card.exportable, card.validation
    errors, _ = validate_design({"attack": card.attack, "health": card.health, "sigils": card.sigil_ids,
                                 "tribe": card.tribe, "blood_cost": card.blood_cost, "subject_kind": card.subject_kind})
    assert errors == []
    failed = [k for k, v in card.validation["checks"].items() if not v["passed"]]
    assert failed == [], {k: card.validation["checks"][k] for k in failed}


def test_1_raven():
    card = design_card(scan("raven", size="medium", textures=["smooth", "glossy"], reflective=True,
                            visible_features=["feathers", "wings", "beak"]))
    assert card.tribe == "Avian" and card.game_tribes == ["Bird"]
    assert card.sigil_ids[0] == "Flying" and card.attack <= 2
    assert_playable(card)


def test_2_wolf():
    card = design_card(scan("grey wolf", size="medium", textures=["fuzzy"], visible_features=["fur", "fangs"]))
    assert card.tribe == "Canine" and card.game_tribes == ["Canine"]
    assert card.attack >= card.health - 2 and card.blood_cost >= 1
    assert_playable(card)


def test_3_beetle():
    card = design_card(scan("beetle", hardness="hard", textures=["glossy", "segmented"], visible_features=["carapace"]))
    assert card.tribe == "Insect" and card.blood_cost <= 1
    assert_playable(card)


def test_4_deer():
    card = design_card(scan("deer", size="large", textures=["fuzzy"], visible_features=["antlers", "hooves"]))
    assert card.tribe == "Hooved" and card.health > card.attack and "Strafe" in card.sigil_ids
    assert_playable(card)


def test_5_snake():
    card = design_card(scan("snake", size="medium", shape="elongated", textures=["smooth", "glossy"], visible_features=["scales"]))
    assert card.tribe == "Reptile" and card.game_tribes == ["Reptile"]
    assert_playable(card)
    venomous = design_card(scan("rattlesnake", size="medium", shape="elongated"))
    assert venomous.sigil_ids == ["Deathtouch"] and venomous.attack == 1
    assert_playable(venomous)


@pytest.mark.parametrize("name,sigil", [("cat", "Sacrificial"), ("goldfish", "Submerge")])
def test_6_cat_or_fish(name, sigil):
    card = design_card(scan(name, textures=["fuzzy"] if name == "cat" else ["smooth", "glossy"]))
    assert card.tribe == "Miscellaneous" and card.game_tribes == [] and sigil in card.sigil_ids
    assert_playable(card)


def test_7_pinecone_is_a_non_animal_with_no_invented_biology():
    card = design_card(PINECONE)
    assert card.subject_kind == "plant" and card.tribe == "Miscellaneous" and card.game_tribes == []
    assert (card.attack, card.health, card.blood_cost, card.sigil_ids) == (0, 3, 1, ["Sharp"])
    assert card.diagnostics["identification"]["traits"] == []
    profile = card.diagnostics["physical_profile"]
    assert not profile["natural_weapon"] and not profile["predator"] and profile["passive_spines"]
    assert not any(word in card.description.lower() for word in ANIMAL_WORDS)
    prompt = make_portrait_prompt(normalize_analysis(PINECONE), card)
    assert "Do not give it a face" in prompt
    assert card.validation_status == "valid"
    assert_playable(card)


def test_8_ambiguous_low_confidence_subject():
    card = design_card(scan("small furry animal", confidence="low", visible_features=["fur"]))
    assert card.tribe == "Miscellaneous" and card.sigils == []
    assert card.rescan_recommended and card.validation_status == "conservative"
    assert card.attack <= 1 and card.health <= 3
    assert_playable(card)


def test_9_multiple_animals():
    card = design_card(scan("a dog and a cat", size="medium"))
    ident = card.diagnostics["identification"]
    assert ident["multiple_subjects"] and ident["tribe_conflict"] and ident["matched_phrase"] == "dog"
    assert card.diagnostics["confidence"]["used"] == "medium" and len(card.sigils) <= 1
    assert card.tribe == "Canine"
    assert_playable(card)


def test_10_contradictory_and_missing_properties():
    data = {"object_name": "turtle", "dominant_material": "organic", "organic": False, "hardness": "hard",
            "flexibility": "flexible", "textures": ["smooth", "rough", "Scaly-ish"], "confidence": "high"}
    card = design_card(data)
    diag = card.diagnostics["normalized_analysis"]
    assert len(diag["contradictions"]) >= 3 and {"sharp", "size", "shape"} <= set(diag["missing"])
    assert card.diagnostics["confidence"]["used"] in {"low", "medium"}
    assert card.exportable and card.source_attributes == data  # original JSON is preserved untouched


def test_person_only_scan_is_rejected_with_rescan():
    card = design_card(scan("hand"))
    assert card.validation_status == "rejected" and not card.exportable and card.rescan_recommended
    with pytest.raises(CardValidationError):
        design_card(scan("hand"), strict=True)


def test_design_is_deterministic_and_ids_are_stable():
    first, second = design_card(PINECONE), design_card(json.dumps(PINECONE))
    assert first.to_dict() == second.to_dict()
    assert design_card(PINECONE, variant=1).card_id != first.card_id


def test_description_is_player_facing_only():
    card = design_card(scan("raven", size="medium"))
    for internal in ("CP", "confidence", "trait", "{", "power"):
        assert internal not in card.description
    assert card.diagnostics["stat_estimate"]["trace"]


def test_ai_proposal_is_validated_by_the_rules():
    def fake_chat(**kwargs):
        assert kwargs["format"] == "json"
        proposal = {"display_name": "Omen Bird", "description": "It remembers your face.", "attack": 4,
                    "health": 3, "sigils": ["Airborne", "Trifurcated Strike", "Scavenger"]}
        return {"message": {"content": json.dumps(proposal)}}

    card = design_card(scan("raven", size="medium"), use_ai=True, ai_chat=fake_chat)
    assert card.display_name == "Omen Bird" and card.description == "It remembers your face."
    assert card.attack == 2  # 4 pulled back to the rules' estimate (1) + tolerance (1)
    assert "SplitStrike" not in card.sigil_ids and "TriStrike" not in card.sigil_ids
    notes = " ".join(card.diagnostics["notes"])
    assert "Trifurcated Strike" in notes and "pulled back" in notes
    assert_playable(card)


def test_ai_proposal_failure_falls_back_to_rules():
    def broken_chat(**kwargs):
        raise ConnectionError("ollama not running")

    card = design_card(PINECONE, use_ai=True, ai_chat=broken_chat)
    assert card.sigil_ids == ["Sharp"] and any("AI proposal unavailable" in n for n in card.diagnostics["notes"])
