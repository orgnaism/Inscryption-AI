# Inscryption-style Object-to-Card Generator — Local FLUX.2 Klein 4B

This **add-on** consumes the `ObjectAnalysis` JSON produced by your existing
`Inscryption-AI-main` camera / Ollama identifier and outputs full fantasy cards.
**The original `camera.py`, `analyzer.py`, `schemas.py`, etc. are not modified.**

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

Then (adjust your `--project-root` path):

```bash
python generate_card.py --project-root ../Inscryption-AI-main --camera --analyze-photo --variants 3
```

This invokes your **original** `camera.capture_object()` and
`analyzer.analyze_object()`, saves their `ObjectAnalysis` data, then uses
local FLUX.2 Klein 4B for artwork and the existing game-stat/card-rendering rules.
No original identifier source files are edited.

## Outputs

Every run writes a folder containing:

```text
variant_1/
  variant_1_prompt.txt
  variant_1_portrait_128.png
  variant_1_full_card.png
  variant_1_card_data.json
variant_2/ ...
variant_3/ ...
manifest.json
```

`manifest.json` has the paths to import into the game. In each card's JSON,
`attack`/`health` remain in the requested 2–4 range, with sigils chosen according
to eligible material/texture rules and blood cost derived from card strength.
The card frame is an original parchment-style interpretation of your reference;
it is not a copy of a game asset. This tool does **not** yet patch FloppyScryption
or load cards into a compiled `.exe`.

## Tests

```bash
python -m pytest -q
```

Unit tests mock the heavyweight image model; end-to-end inference requires an
actual compatible GPU and model download.

### Troubleshooting

- `No module named Flux2KleinPipeline`: install updated `diffusers` as above.
- Out-of-memory: try lower `FLUX_WIDTH=512` and `FLUX_HEIGHT=512`, fewer variants,
  or a device with more memory; set `FLUX_DEVICE=cuda` on NVIDIA.
- If the reference photo matters, **use `--photo`**; the JSON alone cannot
  preserve its exact colors/details beyond the structured attributes.
- Your scanner's Ollama endpoint is entirely separate from this model.
