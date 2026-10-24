# Inscryption AI Card Generator: Act 1 edition

Photograph something, let the local vision model describe it, and get a **balanced
Inscryption Act 1 card** that the game can load through BepInEx + InscryptionAPI.

```
camera.py ──► analyzer.py (Ollama qwen2.5vl) ──► ObjectAnalysis JSON
   │                                                  │
   │        inscryption_card_generator (Python)       ▼
   │   normalize ─► identify subject ─► tribe ─► interpret properties ─► attack/health
   │   ─► sigils (Act 1 allowlist) ─► Card Power ─► blood cost ─► validate / correct
   │   ─► name + description ─► FLUX.2 Klein artwork ─► 114x94 portrait + card preview
   │   ─► export cards/<id>.json + <id>.png
   └──────────────────────────────────────────────────────┐
                                                          ▼
   BepInEx/plugins/ScannedCardsLoader (C#) ─► InscryptionAPI CardManager.New(...) ─► Act 1 card pool
```

| Folder | What it is |
|---|---|
| `camera.py`, `analyzer.py`, `schemas.py`, `test_scan.py` | The original scanner: webcam capture plus Ollama image analysis. |
| `inscryption_card_generator_flux2_klein_4b/inscryption_card_generator_flux2_klein_4b/` | The card generator (Python). Run `generate_card.py` from here. |
| `inscryption_mod/ScannedCardsLoader/` | Companion BepInEx plugin (C#) that registers exported cards in the game. |
| `docs/BALANCING.md` | Every rule: property interpretation, Card Power, costs, tribes, sigil allowlist. |
| `docs/EXAMPLES.md` | Complete pinecone and raven examples produced by the program. |

---

## Setup

### 1. Install dependencies

Use Python 3.10–3.13. FLUX artwork needs PyTorch, which supports 3.10–3.12 best.

```bash
cd inscryption_card_generator_flux2_klein_4b/inscryption_card_generator_flux2_klein_4b
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1    macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

For the rules engine and tests only (no camera, no artwork model), this is enough:
`pip install pydantic Pillow python-dotenv pytest`. Then always use `--dry-run`.

Install the [Ollama](https://ollama.com) app for image analysis, then pull the model:

```bash
ollama pull qwen2.5vl:3b
```

### 2. AI credentials

None. Both models run locally:

- **Ollama** analyzes the image. Choose a different model with `OLLAMA_VISION_MODEL`.
- **FLUX.2 Klein 4B** generates artwork. Weights download from Hugging Face on first use.

Copy `.env.example` to `.env` to change FLUX settings. `.env` is git-ignored.

### 3. Run the generator

From the generator folder:

```bash
python generate_card.py --camera --variants 3
```

`--camera` opens the original `camera.py` window (SPACE to scan, ESC to cancel) and runs
the original `analyzer.py`. The repository root is found automatically. Pass
`--project-root` only if the scanner lives elsewhere.

If the scan is unreliable (low confidence, no recognizable subject, only a person, or a
failed request), you are asked to rescan up to `--rescan-attempts` times (default 2).
After that a conservative card is generated.

### 4. Capture or supply an image

| Command | Use |
|---|---|
| `python generate_card.py --camera` | webcam |
| `python generate_card.py --photo my_photo.jpg --analyze-photo` | existing photo |
| `python generate_card.py --analysis scan.json --photo my_photo.jpg` | existing analysis JSON; the photo is optional and only used as an artwork reference |
| `python ../../test_scan.py` | analysis only, no card (original script) |

### 5. Generate a card

Without the artwork model:

```bash
python generate_card.py --analysis examples/pinecone.json --dry-run --explain
```

Output:

- one line per variant: name, tribe, attack/health, blood, sigils and validation status;
- with `--explain`, how each JSON property was used.

Each `variant_N/` folder contains:

| File | Contents |
|---|---|
| `variant_N_card_data.json` | the full internal card, including validation checks and diagnostics |
| `variant_N_full_card.png` | the card preview |
| `variant_N_portrait_114x94.png` | the in-game portrait |
| `variant_N_registration.cs.txt` | the API calls the mod will make |

Useful flags:

| Flag | Effect |
|---|---|
| `--variants 3` | up to 3 alternatives (different optional sigil or name) |
| `--strict` | refuse instead of falling back to a conservative card |
| `--ai-propose` | let the Ollama model *propose* name, flavor, stats and sigils; the rules still validate and clamp everything |

### 6. Export the card

Every run exports to `<run folder>/mod_export/ScannedCardsLoader/cards/` unless you pass
`--no-export`. To export straight into the game:

```bash
python generate_card.py --camera --export-dir "C:/Program Files (x86)/Steam/steamapps/common/Inscryption/BepInEx/plugins/ScannedCardsLoader/cards"
```

Re-exporting an identical card is harmless. A *different* card with the same id is
refused unless you pass `--overwrite`.

Optional: `--jsonloader-dir <folder>` also writes a JSONLoader `.jldr2` file. Use this
instead of the companion plugin, never both.

### 7. Build and install the mod

The full guide is in [`inscryption_mod/README.md`](inscryption_mod/README.md). In short:

1. Install BepInEx for Inscryption, MonoMod Loader and InscryptionAPI (r2modman makes this easy).
2. Copy `InscryptionAPI.dll` into `inscryption_mod/ScannedCardsLoader/lib/`.
3. Build:

   ```bash
   cd inscryption_mod/ScannedCardsLoader
   dotnet build -c Release
   ```

4. Copy `bin/Release/netstandard2.0/ScannedCardsLoader.dll` and the exported `cards/`
   folder into `Inscryption/BepInEx/plugins/ScannedCardsLoader/`.

### 8. Load and test in Act 1

1. Start the game and check `BepInEx/LogOutput.log` (or the console) for one
   `Registered ScannedCards_<id> ...` line per card, or the reason a file was skipped.
2. Start a new Act 1 run. Generated cards are in the **card choice** and **trader** pools
   (`SetDefaultPart1Card`), so pick cards at choice nodes until one appears.
3. Check that the portrait, cost, stats and sigils match `variant_N_full_card.png`, and
   that the sigils behave as described.

---

## What changed

**Added:**

- `inscryption_card_generator/`:
  - `analysis.py` — parse and normalize;
  - `taxonomy.py` — identify subject, assign tribe;
  - `interpretation.py` — physical evidence;
  - `stats.py` — attack and health;
  - `sigils.py` — selection;
  - `balance.py` — Card Power, cost, validation, correction;
  - `naming.py`;
  - `generator.py` — orchestration;
  - `artwork.py` — 114×94 portrait;
  - `export.py` — mod JSON, JSONLoader, registration preview;
  - `ai_proposer.py` — optional AI proposal, always validated;
  - `config.py`;
  - `data/balance_rules.json`, `data/sigils.json`, `data/taxonomy.json` — all tunable rules.
- `inscryption_mod/ScannedCardsLoader/` — C# plugin, `.csproj`, `NuGet.Config`, READMEs.
- `tests/` — 9 new test modules and `conftest.py`.
- `examples/raven.json` and the `examples/act1_*` example runs.
- `docs/`.

**Changed:**

| File | Change |
|---|---|
| `analyzer.py` | Same function and output. Adds `format="json"`, tolerant JSON extraction, a clear `AnalysisError` when Ollama fails, `OLLAMA_VISION_MODEL`, two optional fields (`visible_features`, `subject_count`), and the instruction to describe the most prominent of several subjects. |
| `schemas.py`, `schema_compat.py` | Same two optional fields, with defaults so older JSON still validates. |
| `test_scan.py` | Prints analysis failures instead of crashing. |
| `pipeline.py` | Same entry point. Now uses the balanced generator and writes the 114×94 portrait, the export and the registration preview. |
| `generate_card.py` | All original flags kept. Adds export, rescan, strict, AI-proposal and explain options, and finds the project root automatically. |
| `rules.py` | Legacy `generate_card_data()` kept but delegates to the new engine. The old version produced random 2–4 stats and invented sigils/tribes (Battery Spark, Bone Heap, Woodland, Construct) that the game cannot load. |
| `renderer.py` | Shows 0–2 sigils, the tribe, one drop per blood and FREE. Fixes the Windows font lookup that rendered tiny text (`arialbd.ttf`). |
| `prompts.py` | Non-animals are drawn as themselves with no face or limbs. Act 1 portrait framing. |
| `flux_local.py` | Can also keep the full-resolution image (`raw_out_path`). |
| `art_api.py` | The dry-run placeholder has no eyes for non-animals. |
| `card_models.py` | Adds `GeneratedCard`; keeps `CardData`. |
| `tests/test_rules.py` | Asserts Act 1 ranges instead of the old random 2–4 rule. |

**Removed:** nothing. The old examples are kept. `__pycache__` folders are left out of the ZIP.

---

## Tests

```bash
cd inscryption_card_generator_flux2_klein_4b/inscryption_card_generator_flux2_klein_4b
python -m pytest -q
```

Result on 2026-10-24 (Windows, Python 3.13.15, pydantic 2.14, Pillow 12.3, pytest 9.1):
**174 passed**. The original 4 tests also passed before any change. The FLUX and Ollama
calls are mocked; no GPU, model download or network was used.

The suite covers:

- JSON parsing and normalization;
- property interpretation;
- classification, including the ten required inputs;
- stat generation;
- cost calibration against 35 vanilla cards;
- sigil allowlist and combinations;
- balancing and correction;
- export, duplicate ids and artwork size;
- the scanner's failure handling;
- C#/Python allowlist consistency.

---

## Limitations

| Area | Status |
|---|---|
| **C# plugin** | Not compiled and not run. No .NET SDK was installed here, by choice. Its API calls were checked line by line against the InscryptionAPI 2.24.1 source. |
| **In-game testing** | Not done. No card has been loaded in Inscryption. |
| **Artwork** | FLUX was not run (no GPU or model download). Examples use the placeholder portrait. Keying out the background assumes a flat background, as the prompt requests. |
| **Real scans** | The camera and Ollama were not run. The pinecone JSON comes from the brief; the other inputs are hand-written analyzer-style JSON. |
| **Kaycee's Mod sigils** | Armored, Double Strike, Scavenger and others are part of the Part 1 ruleset. They may be missing from the base Act 1 rulebook. Behaviour in-game is untested. |
| **Fledgling / Loose Tail** | Use the game's default evolution and tail (no custom `evolveParams`/`tailParams`). |
| **Taxonomy** | About 128 curated entries. Unknown names fall back to Miscellaneous (unidentified creature or plain object). Amphibians are Reptile and spiders Insect by explicit, documented game-taxonomy rules; see `docs/BALANCING.md`. |
| **Bone costs** | Not generated. Every card costs blood (0–3). |
| **Display names** | Can match vanilla names (e.g. "Raven"). Internal ids are always unique (`ScannedCards_<id>`). |
