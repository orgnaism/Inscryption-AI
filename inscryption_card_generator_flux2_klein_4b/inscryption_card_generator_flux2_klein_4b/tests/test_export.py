"""Artwork conversion, mod export, duplicate ids and the dry-run pipeline."""
import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from conftest import PINECONE, scan
from inscryption_card_generator.artwork import ACT1_PORTRAIT_SIZE, check_act1_portrait, make_act1_portrait
from inscryption_card_generator.balance import CardValidationError
from inscryption_card_generator.export import (DuplicateCardIdError, export_card, export_jsonloader,
                                               find_duplicate_ids, registration_snippet)
from inscryption_card_generator.generator import design_card
from inscryption_card_generator.pipeline import run_generation


@pytest.fixture
def portrait(tmp_path):
    src = Image.new("RGB", (768, 768), (200, 200, 200))
    for x in range(250, 520):
        for y in range(200, 600):
            src.putpixel((x, y), (40, 30, 20))
    return make_act1_portrait(src, tmp_path / "art.png")


def test_act1_portrait_is_exactly_114x94_with_transparent_background(portrait):
    img = Image.open(portrait)
    assert img.size == ACT1_PORTRAIT_SIZE and img.mode == "RGBA"
    assert img.getpixel((0, 0))[3] == 0 and img.getpixel((57, 47))[3] == 255
    assert check_act1_portrait(portrait) == []


def test_wrong_size_portrait_is_refused(tmp_path):
    bad = tmp_path / "bad.png"
    Image.new("RGBA", (128, 128)).save(bad)
    assert check_act1_portrait(bad)
    with pytest.raises(CardValidationError):
        export_card(design_card(PINECONE), bad, tmp_path / "cards")


def test_mod_export_contents(tmp_path, portrait):
    card = design_card(PINECONE)
    paths = export_card(card, portrait, tmp_path / "cards")
    data = json.loads(open(paths["card_json"], encoding="utf-8").read())
    assert data == {
        "schema_version": 1, "card_id": card.card_id, "display_name": "Pinecone", "description": card.description,
        "attack": 0, "health": 3, "blood_cost": 1, "tribes": [], "abilities": ["Sharp"],
        "portrait": f"{card.card_id}.png", "tribe_label": "Miscellaneous", "card_power": 5, "validation_status": "valid"}
    assert Image.open(paths["portrait"]).size == (114, 94)
    raven = design_card(scan("raven", size="medium"))
    assert json.loads(open(export_card(raven, portrait, tmp_path / "cards")["card_json"]).read())["tribes"] == ["Bird"]


def test_duplicate_identifiers(tmp_path, portrait):
    card = design_card(PINECONE)
    cards_dir = tmp_path / "cards"
    export_card(card, portrait, cards_dir)
    export_card(card, portrait, cards_dir)  # identical content: idempotent
    changed = replace(card, description="Something else entirely.")
    with pytest.raises(DuplicateCardIdError):
        export_card(changed, portrait, cards_dir)
    export_card(changed, portrait, cards_dir, overwrite=True)
    assert find_duplicate_ids([card, changed, design_card(PINECONE, variant=1)]) == [card.card_id]


def test_rejected_cards_are_never_exported(tmp_path, portrait):
    with pytest.raises(CardValidationError):
        export_card(design_card(scan("hand")), portrait, tmp_path / "cards")


def test_jsonloader_export_fields(tmp_path, portrait):
    paths = export_jsonloader(design_card(PINECONE), portrait, tmp_path / "jl")
    data = json.loads(open(paths["jldr2"], encoding="utf-8").read())
    assert data["modPrefix"] == "ScannedCards" and data["abilities"] == ["Sharp"] and data["tribes"] == []
    assert data["metaCategories"] == ["ChoiceNode", "TraderOffer"] and data["temple"] == "Nature"
    assert data["bloodCost"] == 1 and data["texture"].endswith("_jl.png")


def test_registration_snippet_uses_real_api_calls():
    pine = registration_snippet(design_card(PINECONE))
    assert 'CardManager.New("ScannedCards"' in pine and "SetBloodCost(1)" in pine
    assert "Ability.Sharp" in pine and "AddTribes" not in pine
    assert "AddTribes(Tribe.Bird)" in registration_snippet(design_card(scan("raven", size="medium")))


def test_dry_run_pipeline_writes_every_artifact(tmp_path):
    analysis = tmp_path / "pinecone.json"
    analysis.write_text(json.dumps(PINECONE), encoding="utf-8")
    manifest = run_generation(analysis, tmp_path / "variant_1", use_flux=False, export_dir=tmp_path / "cards",
                              jsonloader_dir=tmp_path / "jl")
    for key in ("card_data", "portrait", "act1_portrait", "full_card", "prompt", "registration_preview"):
        assert Path(manifest[key]).is_file(), key
    assert manifest["validation_status"] == "valid"
    card = json.loads(open(manifest["card_data"], encoding="utf-8").read())
    assert card["artwork_reference"]["generated_by"] == "placeholder (dry run)"
    assert card["diagnostics"]["strict_schema"] == "passed"
    assert sorted(p.suffix for p in (tmp_path / "cards").iterdir()) == [".json", ".png"]


def test_pipeline_records_but_survives_strict_schema_failures(tmp_path):
    analysis = tmp_path / "odd.json"
    analysis.write_text(json.dumps(dict(PINECONE, textures=["Spiky", "rough"])), encoding="utf-8")
    manifest = run_generation(analysis, tmp_path / "v", use_flux=False)
    card = json.loads(open(manifest["card_data"], encoding="utf-8").read())
    assert card["diagnostics"]["strict_schema"].startswith("ValidationError")
    assert card["sigils"][0]["id"] == "Sharp"


def test_pipeline_for_rejected_scan_writes_only_card_data(tmp_path):
    analysis = tmp_path / "hand.json"
    analysis.write_text(json.dumps(scan("hand")), encoding="utf-8")
    manifest = run_generation(analysis, tmp_path / "v", use_flux=False, export_dir=tmp_path / "cards")
    assert manifest["validation_status"] == "rejected" and "act1_portrait" not in manifest
    assert not (tmp_path / "cards").exists()
