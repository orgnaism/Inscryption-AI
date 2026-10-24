"""Card power, blood cost and the validation/correction layer, calibrated on vanilla cards."""
import pytest

from inscryption_card_generator.balance import (balance_design, card_power, required_blood_cost,
                                                validate_design, vanilla_cp_range)
from inscryption_card_generator.config import balance_rules

CALIBRATION = balance_rules()["calibration"]["cards"]


@pytest.mark.parametrize("attack,health,sigils,expected", [
    (3, 2, [], 8),                        # Wolf (guide table)
    (4, 6, [], 14),                       # Grizzly
    (2, 2, ["DeathShield"], 10),          # Mud Turtle
    (1, 2, ["Flying"], 4),                # Sparrow
    (2, 5, ["DoubleStrike"], 13),         # Dire Wolf
    (1, 3, ["Strafe", "SplitStrike"], 10),  # Pronghorn
    (3, 6, ["OpponentBones"], 14),        # guide's 3/6 Scavenger Alligator
    (4, 3, ["Submerge", "StrafeSwap"], 13),  # guide's 4/3 Waterborne Rampager Alligator
])
def test_card_power_formula_matches_the_guide(attack, health, sigils, expected):
    assert card_power(attack, health, sigils) == expected


def test_guide_strix_gets_the_airborne_double_strike_surcharge():
    # Guide: 1/2 Airborne + Double Strike is CP 8, cost bumped for direct-damage risk.
    assert card_power(1, 2, ["Flying", "DoubleStrike"]) == 8 + 2
    assert required_blood_cost(1, 2, ["Flying", "DoubleStrike"])[0] == 2


def test_cost_bands_reproduce_vanilla_blood_costs():
    mismatches = []
    for card in CALIBRATION:
        cost, _ = required_blood_cost(card["attack"], card["health"], card["sigils"])
        if cost != card["blood"]:
            mismatches.append((card["name"], cost, card["blood"], card.get("outlier")))
    assert [m for m in mismatches if not m[3]] == []
    assert {m[0] for m in mismatches} == {"Ring Worm", "Mantis"}  # documented vanilla outliers


def test_band_averages_track_the_guide():
    # Guide averages (which also include bone-cost cards): 1 blood 5.2, 2 blood 8.
    # The 3-blood guide average (10) is pulled down by 5-6 bone cards, so it is not compared here.
    for blood, average in {1: 5.2, 2: 8.0}.items():
        powers = [card_power(c["attack"], c["health"], c["sigils"]) for c in CALIBRATION
                  if c["blood"] == blood and not c.get("outlier")]
        assert abs(sum(powers) / len(powers) - average) <= 1.0, blood
    assert vanilla_cp_range(1) == (3, 6) and vanilla_cp_range(2) == (7, 10) and vanilla_cp_range(3) == (11, 14)


@pytest.mark.parametrize("design,fragment", [
    ({"attack": 7, "health": 2, "sigils": []}, "attack 7 is outside"),
    ({"attack": 1, "health": 0, "sigils": []}, "health 0 is outside"),
    ({"attack": "3", "health": 2, "sigils": []}, "attack must be an integer"),
    ({"attack": 1, "health": 2, "sigils": [], "tribe": "Dragon"}, "tribe 'Dragon'"),
    ({"attack": 1, "health": 2, "sigils": [], "tribe": "Avian", "subject_kind": "plant"}, "cannot have the Avian tribe"),
])
def test_invalid_stats_and_tribes_are_rejected(design, fragment):
    errors, _ = validate_design(design)
    assert any(fragment in e for e in errors), errors


@pytest.mark.parametrize("ability,fragment", [
    ("GainBattery", "requires energy"), ("GemDependant", "requires gems"), ("Brittle", "act2 act3"),
    ("TriStrike", "not allowed on generated cards"), ("MadeUpSigil", "not a known Inscryption ability"),
])
def test_incompatible_sigils_are_rejected(ability, fragment):
    errors, _ = validate_design({"attack": 1, "health": 2, "sigils": [ability]})
    assert any(fragment in e for e in errors), errors


@pytest.mark.parametrize("sigils", [["TripleBlood", "Sacrificial"], ["Deathtouch", "SplitStrike"],
                                    ["Strafe", "WhackAMole"], ["Flying", "Sharp", "Submerge"], ["Sharp", "Sharp"]])
def test_bad_sigil_combinations_are_rejected(sigils):
    errors, _ = validate_design({"attack": 1, "health": 2, "sigils": sigils})
    assert errors


def test_effective_attack_limit_and_correction():
    errors, _ = validate_design({"attack": 3, "health": 3, "sigils": ["DoubleStrike"]})
    assert any("effective attack 6" in e for e in errors)
    fixed = balance_design(3, 3, ["DoubleStrike"])
    assert fixed.attack == 2 and fixed.status == "adjusted"


def test_cost_mismatches_are_detected():
    under, _ = validate_design({"attack": 3, "health": 2, "sigils": [], "blood_cost": 1})
    over, _ = validate_design({"attack": 3, "health": 2, "sigils": [], "blood_cost": 3})
    assert any("under-costed" in e for e in under) and any("over-costed" in e for e in over)
    assert not validate_design({"attack": 3, "health": 2, "sigils": [], "blood_cost": 2})[0]


def test_overpowered_design_is_corrected_not_passed_through():
    result = balance_design(4, 7, ["DeathShield", "Sharp"], "Miscellaneous")
    assert result.status == "adjusted" and result.blood_cost == 3
    assert result.card_power <= 14 and result.adjustments
    assert not validate_design({"attack": result.attack, "health": result.health, "sigils": result.sigils,
                                "blood_cost": result.blood_cost})[0]


def test_disallowed_sigils_are_stripped_by_the_balancer():
    result = balance_design(1, 2, ["Flying", "GainBattery", "TriStrike"], "Avian")
    assert result.sigils == ["Flying"]
    assert any("GainBattery" in a for a in result.adjustments) and any("TriStrike" in a for a in result.adjustments)


def test_free_card_limits():
    assert required_blood_cost(1, 1, [])[0] == 0              # Geck
    assert required_blood_cost(1, 1, ["Flying"])[0] == 1      # free fliers are not allowed
    assert required_blood_cost(0, 1, ["TripleBlood"])[0] == 1  # Black Goat


def test_airborne_attack_cap_and_attack_minimum_costs():
    assert required_blood_cost(2, 1, ["Flying"])[0] == 2
    assert required_blood_cost(3, 1, ["Flying"])[0] == 3
    capped = balance_design(4, 2, ["Flying"], "Avian")
    assert capped.attack == 3 and capped.blood_cost == 3
    assert required_blood_cost(4, 1, [])[0] == 3


def test_canine_minimum_cost():
    assert required_blood_cost(0, 1, [], "Canine")[0] == 1
    assert required_blood_cost(0, 1, [], "Insect")[0] == 0
