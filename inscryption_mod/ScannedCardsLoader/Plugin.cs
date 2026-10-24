using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using BepInEx;
using BepInEx.Logging;
using DiskCardGame;
using InscryptionAPI.Card;
using InscryptionAPI.Helpers;
using UnityEngine;

namespace ScannedCardsLoader
{
    /// <summary>
    /// Registers every card in BepInEx/plugins/ScannedCardsLoader/cards/*.json as an Act 1 card.
    /// The JSON files and their 114x94 portraits are written by generate_card.py, so new cards
    /// need no recompilation: export, restart the game.
    /// </summary>
    [BepInPlugin(PluginGuid, PluginName, PluginVersion)]
    [BepInDependency("cyantist.inscryption.api", BepInDependency.DependencyFlags.HardDependency)]
    public class Plugin : BaseUnityPlugin
    {
        public const string PluginGuid = "scannedcards.inscryption.loader";
        public const string PluginName = "ScannedCardsLoader";
        public const string PluginVersion = "1.0.0";
        public const string ModPrefix = "ScannedCards";  // in-game names are ScannedCards_<card_id>

        internal static ManualLogSource Log;

        private void Awake()
        {
            Log = Logger;
            string cardsDir = Path.Combine(Path.GetDirectoryName(Info.Location), "cards");
            if (!Directory.Exists(cardsDir))
            {
                Log.LogWarning($"No cards folder at {cardsDir}; nothing to register.");
                return;
            }

            var seenIds = new HashSet<string>();
            int registered = 0;
            foreach (string file in Directory.GetFiles(cardsDir, "*.json").OrderBy(f => f, StringComparer.Ordinal))
            {
                string fileName = Path.GetFileName(file);
                ScannedCardDefinition card;
                try
                {
                    card = JsonUtility.FromJson<ScannedCardDefinition>(File.ReadAllText(file));
                }
                catch (Exception e)
                {
                    Log.LogError($"{fileName}: unreadable JSON ({e.Message}); skipped.");
                    continue;
                }

                List<string> problems = CardDefinitionValidator.Validate(card, cardsDir, seenIds);
                if (problems.Count > 0)
                {
                    Log.LogError($"{fileName}: skipped - {string.Join("; ", problems)}");
                    continue;
                }

                try
                {
                    Register(card, cardsDir);
                    seenIds.Add(card.card_id);
                    registered++;
                    Log.LogInfo($"Registered {ModPrefix}_{card.card_id} '{card.display_name}' " +
                                $"{card.attack}/{card.health}, {card.blood_cost} blood, " +
                                $"sigils [{string.Join(", ", card.abilities ?? new string[0])}], " +
                                $"tribe {card.tribe_label} (CP {card.card_power}, {card.validation_status})");
                }
                catch (Exception e)
                {
                    Log.LogError($"{fileName}: registration failed - {e.Message}");
                }
            }
            Log.LogInfo($"{registered} scanned card(s) registered from {cardsDir}");
        }

        private static void Register(ScannedCardDefinition card, string cardsDir)
        {
            Ability[] abilities = ParseEnums<Ability>(card.abilities, "ability");
            Tribe[] tribes = ParseEnums<Tribe>(card.tribes, "tribe");

            // TextureHelper.ConvertTexture does not resize: the portrait must be exactly 114x94.
            Texture2D portrait = TextureHelper.GetImageAsTexture(Path.Combine(cardsDir, card.portrait));
            if (portrait.width != CardDefinitionValidator.PortraitWidth || portrait.height != CardDefinitionValidator.PortraitHeight)
                throw new InvalidDataException($"portrait is {portrait.width}x{portrait.height}, expected " +
                                               $"{CardDefinitionValidator.PortraitWidth}x{CardDefinitionValidator.PortraitHeight}");

            CardInfo info = CardManager.New(ModPrefix, card.card_id, card.display_name, card.attack, card.health, card.description);
            info.SetBloodCost(card.blood_cost);
            info.SetDefaultPart1Card();  // ChoiceNode + TraderOffer meta categories, Nature temple
            if (abilities.Length > 0)
                info.AddAbilities(abilities);
            if (tribes.Length > 0)
                info.AddTribes(tribes);
            info.SetPortrait(portrait);
        }

        private static T[] ParseEnums<T>(string[] names, string label) where T : struct
        {
            var values = new List<T>();
            foreach (string name in names ?? new string[0])
            {
                if (!Enum.IsDefined(typeof(T), name))
                    throw new InvalidDataException($"{label} '{name}' does not exist in this game version");
                values.Add((T)Enum.Parse(typeof(T), name));
            }
            return values.ToArray();
        }
    }
}
