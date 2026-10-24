# Balancing rules, tribes and sigils

Every number below is read from
`inscryption_card_generator/data/*.json` (`balance_rules.json`, `sigils.json`,
`taxonomy.json`). Change those files to tune the generator; no code changes needed.
Set `INSCRYPTION_RULES_DIR` to try an alternative rule folder.

Main reference: *A Treatise on Inscryption Card Creation (for Act I/Kaycee's Mod)*,
r/inscryption (u/Counthulhu). Sigil power levels: Inscryption wiki, *Sigils* page.

## 1. From image JSON to evidence (`interpretation.py`)

The analyzer's JSON describes what the camera saw. It is turned into named evidence
first; stats and sigils are derived only from that evidence.

| JSON property | Rule | Never |
|---|---|---|
| `object_name` | Matched against the taxonomy (longest phrase first, head noun last: "deer skull" is a skull). Gives the kind (animal, plant, object…), the tribe and identity traits (flight, venomous, shell…). | Sets stats on its own. Traits only make bonuses or sigils *eligible*. |
| `size` | Baseline: health tiny 1 / small 2 / medium 3 / large 4. Animal attack: tiny 0 / small 1 / medium 1 / large 2. Predator bonus needs at least medium. | Sets blood cost. Cost comes only from total Card Power. |
| `hardness`, `dominant_material`, `secondary_materials` | One shared **toughness level** (0–2) = the **strongest** of: hardness (soft 0, medium 1, hard 2), dominant material (stone/metal 2; wood/ceramic/leather/rubber/plastic/electronic/mixed 1; others 0), secondary materials (one level weaker). Level 2 gives +1 health. | Stack: "hard" + "metal" + "stone" is still level 2. |
| `flexibility` | Secondary. Rigid + glass/ceramic counts as brittle (−1 health). It also gates blade, spines and tall-structure rules (a flexible object is none of these). | Changes animal stats: soft or flexible animals are not weakened. |
| `textures` | Corroboration only. "sharp" adds to sharpness evidence. ridged/segmented/rough/glossy confirm a shell or carapace the identity already has. | Grants a sigil or stat by itself. |
| `shape` | Blade test (angular/elongated) and tall-structure test (elongated/cylindrical). | Changes stats otherwise ("irregular" is neutral). |
| `sharp` | Sharpness evidence: **strong** when `sharp` and the "sharp" texture agree (or one of them plus a visible spine/blade/weapon), **weak** when only one says so. Then: an *animal* whose identity has claws/fangs/horns/… and whose scan shows sharpness or the weapon gets +1 attack. A rigid, hard, blade-shaped *object* gets +1 attack (objects capped at 1). Any other rigid sharp non-animal gets **passive spines** (Sharp Quills eligible, no attack). | Turns a pinecone's scales into claws. |
| `reflective` | Recorded as descriptive surface evidence. | Changes anything. |
| `organic` | Distinguishes living subjects from objects: an animal name with `organic=false` and an inorganic material is a **depiction** (toy, statue). `organic=false` with `dominant_material=organic` is a contradiction; the material wins. | Chooses a tribe. |
| `electronic` | An animal name with `electronic=true` is a depiction (robot toy). Electronics become plain object cards. | Grants energy or technology mechanics (none exist in Act 1). |
| `confidence` | high: up to 2 sigils. medium: 1 sigil. low: no sigils, no animal tribe, attack ≤ 1, health ≤ 3, rescan recommended. Each 2 contradictions, or 3+ missing physical fields, lowers it one step. A generic name ("object") forces low. Animals from different tribes in one scan lower it one step. | Measures card power. |
| `visible_features` *(new, optional)* | What the camera actually saw (claws, shell, thorns…). It corroborates weapons, shells and spines. | Required: old JSON without it still works, just more conservatively. |
| `subject_count` *(new, optional)* | Marks a group. It is recorded in diagnostics only. | Changes stats. |

Missing values stay **unknown** (`None`), which is different from an explicit `false`.
Unknown fields contribute no evidence and are listed in the card's diagnostics.

### Attack and health (`stats.py`)

```
animal attack = size baseline + 1 (corroborated natural weapon) + 1 (predator, medium+)
object attack = 0 + 1 (blade-like sharp object), capped at 1;  colonies: 0
health        = size baseline + toughness bonus + 1 (corroborated shell/carapace/hide) - 1 (brittle)
```

Tribe conventions from the guide are then applied:

- **Avian:** small birds keep attack ≤ 1.
- **Hooved:** health stays above attack.
- **Canine:** health ≤ attack + 2.
- **Reptile:** shelled reptiles keep attack ≤ 1.

Low confidence caps stats as in the table above.

Every bonus is logged with the field that caused it (`bonus_power_by_field`). The
check *no single attribute dominates* fails if one field adds more than 2 Card Power.

When a sigil represents some evidence, that evidence does not also add stats. Armored
"consumes" the shell's +1 health.

## 2. Card Power and blood cost (`balance.py`)

```
Card Power (CP) = sum(sigil power) + health + 2 x attack  (+ combo surcharge)
```

Blood cost is the **cheapest** band whose limits the card meets:

| Blood | Max CP | Extra limits |
|---|---|---|
| 0 (free) | 3 | attack ≤ 1, ≤ 1 sigil, no offense/evasion sigils |
| 1 | 6 | |
| 2 | 10 | |
| 3 | 14 | maximum for generated cards (4-blood cards are rares like the Urayuli) |

Minimum costs:

- attack 3 needs 2 blood; attack 4 needs 3 blood (the guide's turn-one-kill guard);
- Canine costs at least 1 blood;
- Worthy Sacrifice costs at least 1 blood;
- Airborne attack ≤ cost (free 1, 1 blood 1, 2 blood 2, 3 blood 3).

Combo surcharges:

- Airborne + Double Strike: +2 CP (the guide raises the Strix's cost for this);
- Airborne + Bifurcated: +2 CP;
- Airborne + Blood Lust: +1 CP.

**Calibration.** The bands reproduce the blood cost of all 35 non-outlier vanilla
blood-cost commons in `balance_rules.json → calibration` (Wolf, Elk, Moose Buck,
Grizzly, Mud Turtle, Sparrow, Raven, Adder, …). Two vanilla cards are deliberately
mis-costed and reported as outliers:

- Ring Worm: 0/1 for 1 blood;
- Mantis: CP 7 for 1 blood.

`tests/test_balance.py` checks all of this.

## 3. Validation and correction

Required checks, stored in every card's `validation.checks`:

1. **Stat ranges:** attack 0–4, health 1–7.
2. **Cost matches power:** the card's cost equals the cheapest legal band.
3. **Sigil combination:** allowlisted only, at most 2, no duplicates, no exclusive-group
   or forbidden pair, effective attack (attack × strikes) ≤ 4.
4. **No single attribute dominates:** each JSON field adds ≤ 2 CP.
5. **Tribe appropriate:** non-animals are Miscellaneous; animals have their taxonomy
   tribe (or Miscellaneous when confidence is low).
6. **Plausible in the card pool:** CP lies inside the range of vanilla commons at that cost.

`balance_design` corrects drafts in a fixed order:

1. drop non-allowlisted or duplicate sigils;
2. resolve conflicts;
3. trim to 2 sigils;
4. apply sigil attack overrides (Touch of Death → attack 1);
5. clamp stats;
6. lower attack until effective attack ≤ 4;
7. while no cost fits, apply the first of these that is possible: cap Airborne attack,
   drop the lowest-priority optional sigil, lower whichever stat carries more power.

If the result still fails, the card is **rejected**. Without `--strict` it is replaced by
a conservative 0-attack fallback; with `--strict` an error is raised. Rejected cards are
never exported.

## 4. Tribes (`taxonomy.json`)

| Generator tribe | Game representation | Examples |
|---|---|---|
| Avian | `Tribe.Bird` | raven, owl, sparrow, duck, kingfisher, **egg** (Raven Egg precedent) |
| Canine | `Tribe.Canine` | dog breeds, wolf, coyote, fox |
| Insect | `Tribe.Insect` | ant, bee, beetle, moth, **worms** (Ring Worm precedent), **spiders/scorpions** (see below), beehive |
| Hooved | `Tribe.Hooved` | deer, elk, moose, goat, sheep, bull, horse, pig |
| Reptile | `Tribe.Reptile` | snakes, lizards, turtles, crocodilians, **frogs/toads/tadpoles** (Bullfrog and Tadpole are Reptile in-game), salamanders |
| Miscellaneous | **no tribe** (empty `CardInfo.tribes`) | cats, fish, rodents, bears, **bats** (vanilla Bat has no tribe), crustaceans, and every non-animal |

These decisions follow the game's taxonomy, not strict biology. They were checked
against vanilla cards on the Inscryption wiki.

- **Amphibians → Reptile.** The project brief listed amphibians under Miscellaneous, but
  in the game Bullfrog and Tadpole are Reptile. To change this, edit the `frog` and
  `tadpole` entries in `taxonomy.json`.
- **Spiders → Insect, by an explicit rule.** Arachnids are not insects. However, the game
  defines Insect as "bug-like": Ring Worm, a worm, is Insect. The game has no spider card
  and no arachnid tribe. Every spider/scorpion entry documents this rule in its `note`.
- **Miscellaneous is not a custom tribe.** Registering a new tribe through
  `TribeManager` would change how totems behave. The vanilla game simply leaves 40% of
  its cards tribeless.
- **Bats → Miscellaneous.** They are fliers but not Avian; vanilla Bat has Airborne and no tribe.

Non-animals (plants, food, minerals, objects, remains, depictions) always get
Miscellaneous and no animal traits. People are never turned into cards: a scan whose
only subject is a person is rejected and a rescan is requested.

## 5. Sigils (`sigils.json`)

**Allowlisted:** 36 sigils from the Act I and Kaycee's Mod Nature pool. Each entry
records:

- the game's `Ability` enum id (verified against the enum list in JSONLoader's `Enums.md`);
- the wiki power level;
- the identity trait or physical rule that justifies it.

| Sigil (id) | Power | Justified by |
|---|---|---|
| Airborne (`Flying`) | 0 | flight (Avian signature) |
| Waterborne (`Submerge`) | 1 | aquatic |
| Mighty Leap (`Reach`) | 1 | leaper, tall; or rule *tall_structure* |
| Sprinter (`Strafe`) / Hefty (`StrafePush`) / Rampager (`StrafeSwap`) | 1 | swift / heavy + large / charger (Hooved signatures) |
| Burrower (`WhackAMole`) | 1 | burrower |
| Guardian (`GuardDog`) | 1 | guardian (dogs, geese) |
| Loose Tail (`TailOnHit`) | 2 | tail autotomy (lizards, salamanders) |
| Sharp Quills (`Sharp`) | 2 | quills, thorns; or rule *passive_spines* |
| Stinky (`DebuffEnemy`) | 2 | stench |
| Made of Stone (`MadeOfStone`) | 2 | rule *stone_body* |
| Armored (`DeathShield`) | 4 | shell (turtles, armadillos) |
| Touch of Death (`Deathtouch`) | 4 | venomous (sets attack to 1) |
| Double Strike (`DoubleStrike`) | 4 | raptor (owls, hawks; dire wolf) |
| Bifurcated Strike (`SplitStrike`) | 4 | pincers, forked horns |
| Bone Digger, Scavenger, Corpse Eater, Bone King | 2/2/3/2 | bone digger, scavenger, carrion feeder, bone remains |
| Worthy Sacrifice (`TripleBlood`) | 2 | goats and sheep (min 1 blood) |
| Blood Lust, Leader, Hoarder, Fecundity, Unkillable, Many Lives | 3/3/4/3/2/4 | bloodthirsty, pack leader, hoarder, prolific, indestructible, nine lives |
| Bees Within, Ant Spawner, Rabbit Hole, Dam Builder, Bellist | 3/3/3/3/4 | hive, ant colony, warren, beaver, bell |
| Fledgling (`Evolve`), Brood Parasite (`CreateEgg`), Morsel | 2/4/3 | juvenile, cuckoo/cowbird, edible |
| Annoying (`BuffEnemy`) | −1 | pest (a drawback that buys stats) |

**Never combined:**

- **Exclusive groups:** multi-strike; movement; play-a-card-on-play.
- **Degenerate pairs:**
  - Worthy Sacrifice + Many Lives / Unkillable / Fecundity (infinite blood);
  - Many Lives + Morsel;
  - Touch of Death + Bifurcated / Double Strike / Sharp Quills (multiplied removal);
  - Blood Lust + multi-strike.
- **Contradictory pairs:**
  - Waterborne with any blocker or on-hit sigil;
  - Annoying + Stinky;
  - Airborne + Mighty Leap.

**Valid in Act I but not auto-selected:**

| Sigil | Reason |
|---|---|
| Repulsive (4) | rare-only hard lock |
| Trifurcated Strike (5) | rare-only |
| Amorphous (3) | random, so it cannot be balanced |
| Trinket Bearer (5) | rare-only |
| Steel Trap (5) | Trapper item |
| Frozen Away | needs a second card definition |
| Finical Hatchling | Hydra puzzle |
| Tidal Lock, Omni Strike | boss-only |
| Sinkhole | unused |

**Excluded (incompatible with Act 1):**

- every energy sigil (Conduit*, Cell*, `GainBattery`, `Activated*Energy`);
- every gem sigil (`GainGem*`, `GemDependant`, `ShieldGems`, …);
- Act 2/3, undead and technology sigils (`Brittle`, `Sniper`, `Sentry`, `Haunter`, …).

A test checks that every value of the game's Ability enum falls into one of these three
lists. Another checks that the C# plugin's allowlist matches `sigils.json` exactly.

### Uncertain / unverified

- Kaycee's Mod sigils (Armored, Double Strike, Scavenger, Bone Digger, Rampager, Blood
  Lust, Brood Parasite, Morsel, Made of Stone, Annoying) belong to the Part 1 ruleset.
  They are expected to work in a modded Act 1 run, but they may not appear in the
  base-game Act 1 rulebook. Not tested in-game.
- **Fledgling** without `evolveParams` uses the game's default evolution, the same as a
  Fledgling sigil transferred onto any card. Not tested in-game.
- **Loose Tail** without `tailParams` uses the game's default tail, the same as a
  transferred Loose Tail. Not tested in-game.
