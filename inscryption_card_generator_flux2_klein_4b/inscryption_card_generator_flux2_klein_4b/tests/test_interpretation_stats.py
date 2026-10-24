"""Physical-property interpretation and attack/health estimation."""
import itertools

import pytest

from conftest import OBJECT_BASE, PINECONE, scan
from inscryption_card_generator.analysis import normalize_analysis
from inscryption_card_generator.generator import design_card
from inscryption_card_generator.interpretation import interpret
from inscryption_card_generator.stats import estimate_stats
from inscryption_card_generator.taxonomy import assign_tribe, identify_subject


def profile_and_stats(data, confidence="high"):
    a = normalize_analysis(data)
    i = identify_subject(a)
    p = interpret(a, i)
    return p, estimate_stats(i, p, assign_tribe(i, confidence).tribe, confidence)


def test_overlapping_toughness_evidence_does_not_stack():
    hard_only = profile_and_stats(scan("widget", OBJECT_BASE, dominant_material="plastic", hardness="hard"))
    metal_only = profile_and_stats(scan("widget", OBJECT_BASE, dominant_material="metal", hardness="soft"))
    both = profile_and_stats(scan("widget", OBJECT_BASE, dominant_material="metal", hardness="hard",
                                  secondary_materials=["stone"]))
    assert hard_only[0].toughness_level == metal_only[0].toughness_level == both[0].toughness_level == 2
    assert hard_only[1].health == metal_only[1].health == both[1].health


def test_secondary_material_is_weaker_evidence():
    p, _ = profile_and_stats(scan("widget", OBJECT_BASE, dominant_material="paper", hardness="soft",
                                  secondary_materials=["metal"]))
    assert p.toughness_level == 1


def test_rigid_glass_is_brittle():
    glass, est = profile_and_stats(scan("vase", OBJECT_BASE, dominant_material="glass", hardness="hard"))
    _, plastic = profile_and_stats(scan("vase", OBJECT_BASE, dominant_material="plastic", hardness="hard"))
    assert glass.brittle and est.health == plastic.health - 1


def test_pinecone_sharpness_is_passive_not_a_weapon():
    p, est = profile_and_stats(PINECONE)
    assert p.sharp_evidence == "strong"
    assert p.passive_spines and not p.edge and not p.natural_weapon and not p.predator
    assert est.attack == 0


def test_sharp_blade_object_gets_small_capped_attack():
    knife = scan("knife", OBJECT_BASE, dominant_material="metal", sharp=True, textures=["sharp"], shape="elongated", size="large")
    p, est = profile_and_stats(knife)
    assert p.edge and not p.natural_weapon and est.attack == 1


def test_animal_weapon_bonus_needs_corroboration_from_the_scan():
    _, hidden = profile_and_stats(scan("wolf", size="medium"))
    _, seen = profile_and_stats(scan("wolf", size="medium", visible_features=["fangs"]))
    _, sharp = profile_and_stats(scan("wolf", size="medium", sharp=True, textures=["sharp"]))
    assert seen.attack == sharp.attack == hidden.attack + 1


def test_sharpness_without_a_natural_weapon_adds_no_attack():
    _, plain = profile_and_stats(scan("sparrow"))
    _, sharp = profile_and_stats(scan("sparrow", sharp=True, textures=["sharp"]))
    assert plain.attack == sharp.attack


@pytest.mark.parametrize("field,a,b", [("reflective", True, False), ("flexibility", "rigid", "flexible")])
def test_descriptive_properties_do_not_change_animal_stats(field, a, b):
    _, one = profile_and_stats(scan("raven", **{field: a}))
    _, two = profile_and_stats(scan("raven", **{field: b}))
    assert (one.attack, one.health) == (two.attack, two.health)


def test_scales_alone_do_not_grant_armor():
    card = design_card(scan("garter snake", size="medium", textures=["ridged", "glossy"], visible_features=["scales"],
                            hardness="medium"))
    assert "DeathShield" not in card.sigil_ids


def test_shell_counts_once_when_corroborated():
    smooth = profile_and_stats(scan("box turtle", hardness="hard", textures=["smooth"]))
    ridged = profile_and_stats(scan("box turtle", hardness="hard", textures=["ridged"]))
    assert not smooth[0].protective_structure and ridged[0].protective_structure
    assert ridged[1].health == smooth[1].health + 1
    card = design_card(scan("box turtle", hardness="hard", textures=["ridged"]))
    assert "DeathShield" in card.sigil_ids
    assert any("no double counting" in n for n in card.diagnostics["notes"])


def test_small_and_large_subjects():
    sizes = [profile_and_stats(scan("dog", size=s))[1] for s in ("tiny", "small", "medium", "large")]
    assert [s.health for s in sizes] == sorted(s.health for s in sizes) and sizes[0].health < sizes[-1].health
    assert sizes[0].attack <= sizes[-1].attack


def test_hard_and_soft_materials():
    _, soft = profile_and_stats(scan("cushion", OBJECT_BASE, dominant_material="fabric", hardness="soft", flexibility="flexible"))
    _, hard = profile_and_stats(scan("rock", OBJECT_BASE, dominant_material="stone", hardness="hard"))
    assert hard.health > soft.health


def test_organic_and_inorganic_versions_of_the_same_name():
    living = design_card(scan("duck", size="medium"))
    rubber = design_card(scan("duck", size="medium", organic=False, dominant_material="rubber"))
    assert living.subject_kind == "animal" and living.tribe == "Avian" and "Flying" in living.sigil_ids
    assert rubber.subject_kind == "depiction" and rubber.tribe == "Miscellaneous" and rubber.sigils == []
    assert rubber.attack == 0


def test_hooved_keep_health_above_attack():
    _, est = profile_and_stats(scan("bull", size="large", sharp=True, textures=["sharp"], visible_features=["horns"]))
    assert est.health > est.attack


def test_low_confidence_caps_stats():
    _, est = profile_and_stats(scan("grizzly bear", size="large", confidence="low", visible_features=["claws"]), "low")
    assert est.attack <= 1 and est.health <= 3


def test_no_single_attribute_dominates_across_many_scans():
    names = ["wolf", "grizzly bear", "box turtle", "knife", "rock", "pinecone", "raven", "stag beetle", "bull"]
    for name, size, hardness, sharp in itertools.product(names, ["tiny", "large"], ["soft", "hard"], [True, False]):
        _, est = profile_and_stats(scan(name, size=size, hardness=hardness, sharp=sharp,
                                        textures=["sharp", "ridged"] if sharp else ["smooth"]))
        assert max(est.bonus_power_by_field.values(), default=0) <= 2, (name, size, hardness, sharp, est.bonus_power_by_field)
