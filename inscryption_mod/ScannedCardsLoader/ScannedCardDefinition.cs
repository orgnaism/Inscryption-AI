using System;

namespace ScannedCardsLoader
{
    /// <summary>
    /// One exported card, as written by inscryption_card_generator/export.py (card_to_mod_json).
    /// Field names match the JSON keys because Unity's JsonUtility maps public fields by name.
    /// </summary>
    [Serializable]
    public class ScannedCardDefinition
    {
        public int schema_version;
        public string card_id;
        public string display_name;
        public string description;
        public int attack;
        public int health;
        public int blood_cost;
        public string[] tribes;     // DiskCardGame.Tribe names; empty = no tribe ("Miscellaneous")
        public string[] abilities;  // DiskCardGame.Ability names
        public string portrait;     // file name of a 114x94 PNG in the same cards folder

        // Informational only (logged, not used for registration).
        public string tribe_label;
        public int card_power;
        public string validation_status;
    }
}
