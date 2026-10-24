# Inscryption-style Object-to-Card Generator — Local FLUX.2 Klein 4B

This **add-on** consumes the `ObjectAnalysis` JSON produced by your existing
`Inscryption-AI-main` camera / Ollama identifier and outputs **balanced Inscryption Act 1
cards** that the companion `ScannedCardsLoader` BepInEx plugin registers in the game.

The repository README (`../../README.md`) has the full setup, from installing to playing
in Act 1. `../../docs/BALANCING.md` lists every rule, and `../../docs/EXAMPLES.md` has
complete pinecone and raven examples.

Pipeline: normalize JSON → identify the subject → tribe → interpret physical properties →
attack/health → Act 1 sigils → Card Power → blood cost → validate/correct → name and
description → FLUX artwork → 114×94 portrait → export for the mod. Each stage is its own
module in `inscryption_card_generator/`, and all numbers live in
`inscryption_card_generator/data/*.json`.

The original `camera.py` and `analyzer.py` are still called as-is. `analyzer.py` and
`schemas.py` gained two optional, backward-compatible fields (`visible_features`,
`subject_count`) and clearer error handling.

**Artwork is generated on your computer by `black-forest-labs/FLUX.2-klein-4B`,**
not OpenAI. The first run downloads model weights; afterward inference runs
locally/offline when the weights are cached. No API key, per-image image-service
fees, or Internet connection are needed after setup.

## Requirements and machine compatibility

- Python 3.10–3.12 recommended, modern NVIDIA GPU strongly recommended.
- Official ComfyUI benchmarks list the 4B distilled model at ~8.4 GB VRAM
  on their test setup; real GPU/RAM needs vary and model offload adds system RAM usage.
- On Apple Silicon, PyTorch MPS may run but can be slower and memory-heavy;
  compatibility varies. CPU mode is technically supported but very slow.
- This project uses **Hugging Face Diffusers**, **not Ollama for image generation**.
  Current Ollama versions have removed experimental image generation. Your existing
  Qwen2.5-VL Ollama *object identifier* remains unchanged and still works.

Model: https://huggingface.co/black-forest-labs/FLUX.2-klein-4B

Setup reference: https://huggingface.co/docs/diffusers/main/api/pipelines/flux2

## Install

1. Install appropriate PyTorch for your NVIDIA CUDA, macOS, or CPU environment:
   https://pytorch.org/get-started/locally/
2. Create a virtual environment, activate it, then install:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

The requirements install current `diffusers` from GitHub because FLUX.2 Klein's
pipeline support may be newer than packaged diffusers releases. For a production
release, pin this to a tested Git commit.

Optional: copy `.env.example` to `.env` to customize device, model, image size,
steps, or local model folder (`FLUX_MODEL_ID`).

## A. Test the card renderer without model downloads

```bash
python generate_card.py --analysis examples/pinecone.json --variants 3 --dry-run
```

Outputs three **placeholder** creature images and cards. No AI generation.

## B. Generate a card from your existing JSON (and optional photo)

```bash
python generate_card.py --analysis path/to/object_analysis.json --photo path/to/photo.jpg --variants 3
```

The original **photo AND JSON-based text prompt** are passed to FLUX.2 Klein.
If no `--photo` is supplied, it uses JSON text only.

Set `--device cuda`, `--device mps`, or `--device cpu` to override automatic selection:

```bash
python generate_card.py --analysis examples/pinecone.json --photo photo.jpg --variants 3 --device cuda
```

The pipeline is loaded **once** and reused for all three variations in the same run.
The model is a large download, and local inference requires significant GPU/RAM.
The example output included in the ZIP is a **placeholder dry-run**, not a FLUX inference.

## C. Use your unmodified scanner and Ollama vision AI

Start Ollama and ensure your existing `qwen2.5vl:3b` identifier model is installed:

```bash
ollama pull qwen2.5vl:3b
```

Then:

```bash
python generate_card.py --camera --variants 3
```

This invokes your **original** `camera.capture_object()` and
`analyzer.analyze_object()`, saves their `ObjectAnalysis` data, then uses the Act 1
rules engine and local FLUX.2 Klein 4B for artwork. The repository root (with
`camera.py`/`analyzer.py`) is found automatically; `--project-root` overrides it.
A low-confidence or unusable scan triggers up to `--rescan-attempts` (default 2) retakes.

## Outputs

Every run writes a folder containing:

```text
variant_1/
  variant_1_prompt.txt
  variant_1_portrait_128.png        # preview portrait (FLUX, pixelized)
  variant_1_art_raw.png             # full-resolution FLUX output (not written in --dry-run)
  variant_1_portrait_114x94.png     # Act 1 in-game portrait (exact size InscryptionAPI expects)
  variant_1_full_card.png           # rendered card preview
  variant_1_card_data.json          # internal card: stats, sigils, validation checks, diagnostics
  variant_1_registration.cs.txt     # the InscryptionAPI calls the mod makes for this card
variant_2/ ...
mod_export/ScannedCardsLoader/cards/<card_id>.json + <card_id>.png   # copy into BepInEx/plugins/ScannedCardsLoader/
manifest.json
```

Attack (0–4), health (1–7), blood cost (0–3) and 0–2 sigils come from the deterministic
rules in `docs/BALANCING.md`, calibrated against vanilla Act 1 cards. Options:

| Option | Effect |
|---|---|
| `--export-dir` | export straight into the game's plugin folder |
| `--no-export` | do not write mod files |
| `--jsonloader-dir` | write a JSONLoader `.jldr2` file instead of using the companion plugin |
| `--strict` | reject instead of falling back to a conservative card |
| `--ai-propose` | the Ollama model proposes a design; the rules validate it |
| `--explain` | print how each JSON property was interpreted |
| `--overwrite` | replace an exported card that has the same id |

The card frame is an original parchment-style interpretation of your reference; it is
not a copy of a game asset.

## Tests

```bash
python -m pytest -q
```

Unit tests mock the heavyweight image model and Ollama. They cover the ten required
inputs (raven, wolf, beetle, deer, snake, cat/fish, pinecone, low confidence, multiple
animals, contradictory/missing data), calibration against vanilla cards, the sigil
allowlist, export and duplicate ids. End-to-end inference still needs a compatible GPU
and the model download, and the mod itself needs a game install to verify.

### Troubleshooting

- `No module named Flux2KleinPipeline`: install updated `diffusers` as above.
- Out-of-memory: try lower `FLUX_WIDTH=512` and `FLUX_HEIGHT=512`, fewer variants,
  or a device with more memory; set `FLUX_DEVICE=cuda` on NVIDIA.
- If the reference photo matters, **use `--photo`**; the JSON alone cannot
  preserve its exact colors/details beyond the structured attributes.
- Your scanner's Ollama endpoint is entirely separate from this model.
