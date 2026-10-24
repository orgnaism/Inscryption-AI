"""Subject identification and tribe assignment."""
import pytest

from conftest import OBJECT_BASE, PINECONE, scan
from inscryption_card_generator.analysis import normalize_analysis
from inscryption_card_generator.config import GENERATOR_TRIBES, taxonomy_table
from inscryption_card_generator.taxonomy import assign_tribe, confidence_after_identification, identify_subject


def ident(name, **kw):
    return identify_subject(normalize_analysis(scan(name, **kw)))


@pytest.mark.parametrize("name,tribe", [
    ("raven", "Avian"), ("crows", "Avian"), ("great grey owl", "Avian"), ("kingfisher", "Avian"),
    ("grey wolf", "Canine"), ("golden retriever", "Canine"), ("red fox", "Canine"), ("coyote", "Canine"),
    ("stag beetle", "Insect"), ("ladybug", "Insect"), ("honeybee", "Insect"), ("moths", "Insect"),
    ("white-tailed deer", "Hooved"), ("moose", "Hooved"), ("goat", "Hooved"), ("bison", "Hooved"),
    ("garter snake", "Reptile"), ("rattlesnake", "Reptile"), ("box turtle", "Reptile"), ("gecko", "Reptile"),
    ("cat", "Miscellaneous"), ("goldfish", "Miscellaneous"), ("field mice", "Miscellaneous"), ("raccoon", "Miscellaneous"),
])
def test_animals_get_their_tribe(name, tribe):
    i = ident(name)
    assert i.is_animal and i.kind == "animal"
    assert assign_tribe(i, "high").tribe == tribe


@pytest.mark.parametrize("name,tribe,why", [
    ("bullfrog", "Reptile", "game precedent: Bullfrog is Reptile"),
    ("tadpole", "Reptile", "game precedent: Tadpole is Reptile"),
    ("salamander", "Reptile", "lizard-like amphibian, Bullfrog precedent"),
    ("bat", "Miscellaneous", "game precedent: Bat has Airborne but no tribe"),
    ("earthworm", "Insect", "game precedent: Ring Worm is Insect"),
    ("spider", "Insect", "explicit arachnid rule (Ring Worm precedent), not keyword matching"),
    ("spider monkey", "Miscellaneous", "longest phrase wins: not a spider"),
    ("catfish", "Miscellaneous", "a fish, not a cat"),
    ("horse fly", "Insect", "an insect, not a horse"),
    ("seahorse", "Miscellaneous", "a fish, not hooved"),
    ("guinea pig", "Miscellaneous", "a rodent, not a pig"),
    ("crayfish", "Miscellaneous", "aquatic crustacean kept tribeless"),
])
def test_game_taxonomy_edge_cases(name, tribe, why):
    assert assign_tribe(ident(name), "high").tribe == tribe, why


def test_spider_rule_is_documented_on_the_entry():
    notes = " ".join(ident("spider").notes)
    assert "Ring Worm" in notes and "arachnid" in notes


def test_pinecone_is_a_plant_not_an_animal():
    i = identify_subject(normalize_analysis(PINECONE))
    assert i.kind == "plant" and not i.is_animal and i.traits == []
    t = assign_tribe(i, "high")
    assert t.tribe == "Miscellaneous" and t.game_tribes == []


@pytest.mark.parametrize("name,overrides,kind", [
    ("toy dog", {}, "depiction"),
    ("raven statue", {}, "depiction"),
    ("duck", {"organic": False, "dominant_material": "rubber"}, "depiction"),
    ("dog", {"electronic": True, "dominant_material": "electronic"}, "depiction"),
    ("dog toy", {}, "depiction"),       # head noun "toy" is a depiction word
    ("computer mouse", {"electronic": True}, "object"),
    ("deer skull", {}, "remains"),       # head noun is "skull"
])
def test_depictions_and_objects_are_not_animals(name, overrides, kind):
    i = ident(name, **overrides)
    assert i.kind == kind and not i.is_animal
    if kind == "depiction":
        assert i.traits == []
    assert assign_tribe(i, "high").tribe == "Miscellaneous"


def test_depiction_keeps_a_descriptive_name():
    assert ident("raven statue").names == ["Raven Statue"]


def test_multiple_animals_first_named_is_primary_and_conflict_lowers_confidence():
    i = ident("a dog and a cat")
    assert i.matched_phrase == "dog" and i.multiple_subjects and i.tribe_conflict
    assert confidence_after_identification(i, "high")[0] == "medium"
    same_tribe = ident("wolf and coyote")
    assert same_tribe.multiple_subjects and not same_tribe.tribe_conflict


def test_groups_of_one_species_and_background_objects():
    pack = ident("pack of wolves")
    assert pack.matched_phrase == "wolves" and pack.is_group and not pack.multiple_subjects
    perched = ident("bird on a branch")
    assert perched.matched_phrase == "bird" and not perched.multiple_subjects
    assert ident("raven", subject_count=3).is_group


def test_people_are_skipped_or_rejected():
    assert not ident("hand").supported
    held = identify_subject(normalize_analysis(dict(PINECONE, object_name="hand holding a pinecone")))
    assert held.supported and held.matched_phrase == "pinecone"


def test_unknown_subjects_use_safe_fallbacks():
    creature = ident("glorpfish", visible_features=["fur", "claws"])
    assert creature.kind == "animal" and assign_tribe(creature, "high").tribe == "Miscellaneous"
    assert ident("glorp").kind == "unknown"
    assert identify_subject(normalize_analysis(scan("widget", OBJECT_BASE))).kind == "object"


def test_low_confidence_never_assigns_an_animal_tribe():
    t = assign_tribe(ident("raven"), "low")
    assert t.tribe == "Miscellaneous" and "low confidence" in t.reason


def test_tribe_game_ids_match_the_game_enum():
    ids = taxonomy_table()["tribe_game_ids"]
    assert ids == {"Avian": ["Bird"], "Canine": ["Canine"], "Insect": ["Insect"], "Hooved": ["Hooved"],
                   "Reptile": ["Reptile"], "Miscellaneous": []}
    for entry in taxonomy_table()["subjects"]:
        assert entry["tribe"] in GENERATOR_TRIBES or entry["kind"] == "human"
        if entry["kind"] not in {"animal", "colony", "human"}:
            assert entry["tribe"] == "Miscellaneous", entry["match"]
