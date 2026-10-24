# ScannedCardsLoader — companion BepInEx plugin

Registers the cards exported by `generate_card.py` as **Act 1 (Leshy's cabin)** cards
through [InscryptionAPI](https://github.com/InscryptionModding/InscryptionAPI).

> **Status:** source only. It was **not compiled or run** in the environment where it
> was written (no .NET SDK, no game install). Every API call it makes was checked
> against the InscryptionAPI source (v2.24.1); see "What was verified" below.

## How it works

At game start (`Awake`), the plugin reads every `cards/*.json` file next to its DLL:

```
BepInEx/plugins/ScannedCardsLoader/
  ScannedCardsLoader.dll
  cards/
    pinecone_5314059f.json   <- written by generate_card.py
    pinecone_5314059f.png    <- 114x94 portrait
```

For each file it re-checks the structural limits (`CardDefinitionValidator.cs`), then calls:

```csharp
CardInfo info = CardManager.New("ScannedCards", card_id, display_name, attack, health, description);
info.SetBloodCost(blood_cost);
info.SetDefaultPart1Card();          // ChoiceNode + TraderOffer, CardTemple.Nature
info.AddAbilities(Ability.Sharp);    // parsed from the JSON names
info.AddTribes(Tribe.Bird);          // skipped for Miscellaneous (no tribe)
info.SetPortrait(texture114x94);
```

New scans need no recompilation: export the card, then restart the game.

## Build

Requirements: .NET SDK 6+ (any SDK that can build `netstandard2.0`) and `InscryptionAPI.dll`
(see `ScannedCardsLoader/lib/README.md`).

```bash
cd inscryption_mod/ScannedCardsLoader
dotnet build -c Release
```

Output: `bin/Release/netstandard2.0/ScannedCardsLoader.dll`. NuGet sources (nuget.org,
nuget.bepinex.dev, nuget.windows10ce.com) and package versions follow the InscryptionAPI
wiki's getting-started page.

## Install

1. Install BepInEx for Inscryption (`BepInExPack_Inscryption`), MonoMod Loader and
   **InscryptionAPI** (`API_dev-API`), e.g. with r2modman / Thunderstore Mod Manager.
2. Create `Inscryption/BepInEx/plugins/ScannedCardsLoader/` and copy
   `ScannedCardsLoader.dll` into it.
3. Copy the exported `cards/` folder into the same place, or run the generator with
   `--export-dir "<Inscryption>/BepInEx/plugins/ScannedCardsLoader/cards"`.
4. Start the game. The BepInEx console/log (`BepInEx/LogOutput.log`) lists each
   `Registered ScannedCards_<id> ...` line, or the reason a file was skipped.

Do not also install the optional JSONLoader `.jldr2` export for the same cards, or they will be registered twice.

## Testing in Act 1

Generated cards use `SetDefaultPart1Card()`, so they enter the normal **card choice**
and **trader** pools. To see one quickly, start a new Act 1 run and pick cards at choice
nodes; with only a few custom cards among the whole vanilla pool, it can take several
nodes. Check in-game that:

- the portrait, name, attack/health and blood drops match the generated card preview;
- the sigils behave as described (e.g. Sharp Quills damages an attacker);
- tribe totems affect the card when it has a tribe.

## What was verified (and how)

| Item | Source |
|---|---|
| `CardManager.New(modPrefix, name, displayName, attack, health, description)` and the `prefix_name` card naming | `InscryptionAPI/Card/CardManager.cs` |
| `SetBloodCost`, `SetDefaultPart1Card` (ChoiceNode + TraderOffer + Nature temple), `AddAbilities`, `AddTribes` | `CardExtensionsSetters.cs`, `CardExtensions.cs` |
| `SetPortrait(Texture2D, FilterMode?)`, `TextureHelper.GetImageAsTexture(string)` | `CardExtensionsPortraits.cs`, `Helpers/TextureHelper.cs` |
| Portrait sprite rect 114x94, no resizing | `TextureHelper.SpriteType.CardPortrait` |
| API plugin GUID `cyantist.inscryption.api` | `InscryptionAPIPlugin.cs` |
| Ability and Tribe enum names | JSONLoader `Enums.md` (lists the enum shipped with the game) |

Not verified: compilation, loading in a real game, and in-game behaviour of each sigil on these cards.
