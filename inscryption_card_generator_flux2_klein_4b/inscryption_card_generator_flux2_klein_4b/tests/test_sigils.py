"""Act 1 sigil allowlist and selection."""
import re

import pytest

from conftest import OBJECT_BASE, PINECONE, REPO_ROOT, scan
from inscryption_card_generator.config import all_known_ability_ids, selectable_sigils, sigil_table
from inscryption_card_generator.generator import design_card
from inscryption_card_generator.sigils import SigilChoice, conflict_reason, select_sigils

# DiskCardGame.Ability enum names as listed in JSONLoader's Enums.md
# (github.com/MADH95/JSONLoader, Thunderstore-Package-Elements/Enums.md).
GAME_ABILITY_ENUM = set("""
ActivatedDealDamage ActivatedDrawSkeleton ActivatedEnergyToBones ActivatedHeal ActivatedRandomPowerBone
ActivatedRandomPowerEnergy ActivatedSacrificeDrawCards ActivatedStatsUp ActivatedStatsUpEnergy AllStrike
Apparition BeesOnHit BombSpawner BoneDigger Brittle BuffEnemy BuffGems BuffNeighbours CellBuffSelf
CellDrawRandomCardOnDeath CellTriStrike ConduitBuffAttack ConduitEnergy ConduitFactory ConduitHeal ConduitNull
ConduitSpawnGems CorpseEater CreateBells CreateDams CreateEgg DeathShield Deathtouch DebuffEnemy DeleteFile
DoubleDeath DoubleStrike DrawAnt DrawCopy DrawCopyOnDeath DrawNewHand DrawRabbits DrawRandomCardOnDeath
DrawVesselOnHit DropRubyOnDeath EdaxioArms EdaxioHead EdaxioLegs EdaxioTorso Evolve ExplodeGems ExplodeOnDeath
ExplodingCorpse FileSizeDamage Flying GainAttackOnKill GainBattery GainGemBlue GainGemGreen GainGemOrange
GainGemTriple GemDependant GemsDraw GuardDog Haunter HydraEgg IceCube LatchBrittle LatchDeathShield
LatchExplodeOnDeath Loot MadeOfStone Morsel MoveBeside OpponentBones PermaDeath PreventAttack QuadrupleBones
RandomAbility RandomConsumable Reach Sacrificial Sentry Sharp ShieldGems Sinkhole SkeletonStrafe Sniper
SplitStrike SquirrelOrbit SquirrelStrafe SteelTrap Strafe StrafePush StrafeSwap Submerge SubmergeSquid SwapStats
TailOnHit Transformer TripleBlood TriStrike Tutor VirtualReality WhackAMole
""".split())


def test_every_id_is_a_real_game_enum_name():
    assert all_known_ability_ids() <= GAME_ABILITY_ENUM


def test_every_game_ability_is_classified():
    assert GAME_ABILITY_ENUM <= all_known_ability_ids()  # selectable, not auto-selected, or excluded


def test_energy_gem_and_other_act_sigils_are_never_selectable():
    excluded = set().union(*sigil_table()["excluded"].values())
    assert not excluded & set(selectable_sigils())
    assert {"GainBattery", "ConduitEnergy", "GemDependant", "GainGemBlue", "Brittle", "Sniper"} <= excluded


@pytest.mark.parametrize("ability,power", [("Flying", 0), ("Submerge", 1), ("Sharp", 2), ("DeathShield", 4),
                                           ("Deathtouch", 4), ("SplitStrike", 4), ("Tutor", 4), ("BuffEnemy", -1)])
def test_power_levels_match_the_wiki(ability, power):
    assert selectable_sigils()[ability]["power"] == power


def test_csharp_plugin_allowlist_matches_python():
    source = (REPO_ROOT / "inscryption_mod" / "ScannedCardsLoader" / "CardDefinitionValidator.cs").read_text(encoding="utf-8")
    block = re.search(r"AllowedAbilities\s*=\s*\{(.*?)\};", source, re.S).group(1)
    assert re.findall(r'"(\w+)"', block) == list(selectable_sigils())


def test_pinecone_gets_sharp_quills_for_its_physical_spines():
    card = design_card(PINECONE)
    assert card.sigil_ids == ["Sharp"]
    assert "passive_spines" in card.sigils[0]["reason"]


def test_texture_keyword_alone_never_grants_a_sigil():
    soft_sharp_texture = scan("cushion", OBJECT_BASE, dominant_material="fabric", hardness="soft",
                              flexibility="flexible", textures=["sharp"], sharp=False)
    assert design_card(soft_sharp_texture).sigils == []


def test_zero_sigil_cards():
    for name in ("grizzly bear", "wolf", "hamster"):
        assert design_card(scan(name, size="medium")).sigils == [], name
    assert design_card(scan("teacup", OBJECT_BASE)).sigils == []


def test_multiple_sigil_card_and_confidence_limits():
    high = design_card(scan("raven", size="medium"))
    assert high.sigil_ids == ["Flying", "OpponentBones"]
    medium = design_card(scan("raven", size="medium", confidence="medium"))
    assert medium.sigil_ids == ["Flying"]  # tribe signature sigil first
    low = design_card(scan("raven", size="medium", confidence="low"))
    assert low.sigils == []


def test_depictions_get_no_animal_sigils():
    assert design_card(scan("toy raven")).sigils == []


def test_conflicting_candidates_are_never_combined():
    choices = [SigilChoice("TripleBlood", "Worthy Sacrifice", 2, "utility", 85, False, "t"),
               SigilChoice("Sacrificial", "Many Lives", 4, "utility", 88, False, "t"),
               SigilChoice("Strafe", "Sprinter", 1, "mobility", 60, False, "t"),
               SigilChoice("WhackAMole", "Burrower", 1, "defense", 50, False, "t")]
    chosen, notes = select_sigils(choices, "high")
    ids = [c.id for c in chosen]
    assert ids == ["Sacrificial", "Strafe"]
    assert conflict_reason("TripleBlood", "Sacrificial") and conflict_reason("Strafe", "WhackAMole")
    assert any("Worthy Sacrifice" in n for n in notes)


def test_variants_rotate_optional_sigils():
    # A goose can justify Guardian or Waterborne; variants offer both, Airborne stays first.
    cards = [design_card(scan("goose", size="medium"), variant=v) for v in range(2)]
    assert [c.sigil_ids for c in cards] == [["Flying", "GuardDog"], ["Flying", "Submerge"]]
    assert cards[0].card_id != cards[1].card_id
