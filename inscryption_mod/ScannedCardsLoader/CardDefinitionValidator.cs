using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;

namespace ScannedCardsLoader
{
    /// <summary>
    /// Structural safety net for exported cards. Balancing is decided by the Python generator;
    /// this re-checks the limits so a hand-edited or corrupted file cannot register an invalid card.
    /// Uses no game types, so the rules are readable and testable on their own.
    /// </summary>
    public static class CardDefinitionValidator
    {
        public const int SupportedSchemaVersion = 1;
        public const int PortraitWidth = 114;   // InscryptionAPI TextureHelper SpriteType.CardPortrait rect
        public const int PortraitHeight = 94;
        public const int MaxAttack = 4, MinHealth = 1, MaxHealth = 7, MaxBloodCost = 3, MaxAbilities = 2;

        // Mirrors "selectable" in inscryption_card_generator/data/sigils.json.
        // tests/test_sigils.py fails if the two lists drift apart.
        public static readonly string[] AllowedAbilities =
        {
            "Flying", "Submerge", "Reach", "Strafe", "StrafePush", "StrafeSwap", "WhackAMole", "GuardDog",
            "TailOnHit", "Sharp", "DebuffEnemy", "MadeOfStone", "DeathShield", "Deathtouch", "DoubleStrike",
            "SplitStrike", "BoneDigger", "OpponentBones", "CorpseEater", "QuadrupleBones", "TripleBlood",
            "GainAttackOnKill", "BuffNeighbours", "Tutor", "DrawCopy", "DrawCopyOnDeath", "Sacrificial",
            "BeesOnHit", "DrawAnt", "DrawRabbits", "CreateDams", "CreateBells", "Evolve", "CreateEgg",
            "Morsel", "BuffEnemy"
        };

        // DiskCardGame.Tribe names for the five Act 1 animal tribes. "Miscellaneous" = no tribe.
        public static readonly string[] AllowedTribes = { "Bird", "Canine", "Hooved", "Insect", "Reptile" };

        private static readonly Regex IdPattern = new Regex("^[a-z0-9_]{1,64}$");

        public static List<string> Validate(ScannedCardDefinition card, string cardsDir, ICollection<string> seenIds)
        {
            var problems = new List<string>();
            if (card == null)
            {
                problems.Add("file is empty or not a card definition");
                return problems;
            }
            if (card.schema_version != SupportedSchemaVersion)
                problems.Add($"schema_version {card.schema_version} is not supported (expected {SupportedSchemaVersion})");
            if (card.card_id == null || !IdPattern.IsMatch(card.card_id))
                problems.Add($"card_id '{card.card_id}' must match {IdPattern}");
            else if (seenIds.Contains(card.card_id))
                problems.Add($"duplicate card_id '{card.card_id}'");
            if (string.IsNullOrWhiteSpace(card.display_name) || card.display_name.Length > 32)
                problems.Add("display_name must be 1-32 characters");
            if (card.attack < 0 || card.attack > MaxAttack)
                problems.Add($"attack {card.attack} outside 0-{MaxAttack}");
            if (card.health < MinHealth || card.health > MaxHealth)
                problems.Add($"health {card.health} outside {MinHealth}-{MaxHealth}");
            if (card.blood_cost < 0 || card.blood_cost > MaxBloodCost)
                problems.Add($"blood_cost {card.blood_cost} outside 0-{MaxBloodCost}");

            string[] abilities = card.abilities ?? new string[0];
            if (abilities.Length > MaxAbilities)
                problems.Add($"{abilities.Length} abilities (max {MaxAbilities})");
            var seenAbilities = new HashSet<string>();
            foreach (string ability in abilities)
            {
                if (Array.IndexOf(AllowedAbilities, ability) < 0)
                    problems.Add($"ability '{ability}' is not on the Act 1 allowlist");
                if (!seenAbilities.Add(ability))
                    problems.Add($"ability '{ability}' listed twice");
            }

            string[] tribes = card.tribes ?? new string[0];
            if (tribes.Length > 1)
                problems.Add("a generated card has at most one tribe");
            foreach (string tribe in tribes)
                if (Array.IndexOf(AllowedTribes, tribe) < 0)
                    problems.Add($"tribe '{tribe}' is not an Act 1 tribe");

            if (string.IsNullOrEmpty(card.portrait) || card.portrait != Path.GetFileName(card.portrait))
                problems.Add("portrait must be a plain file name inside the cards folder");
            else if (!File.Exists(Path.Combine(cardsDir, card.portrait)))
                problems.Add($"portrait '{card.portrait}' not found");
            return problems;
        }
    }
}
