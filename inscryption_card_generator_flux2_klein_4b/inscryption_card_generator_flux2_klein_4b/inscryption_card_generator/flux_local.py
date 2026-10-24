"""Local (not Ollama, not OpenAI) FLUX.2 Klein 4B portrait generation.

Hugging Face Diffusers' Flux2KleinPipeline can condition on both a prompt and
an input photograph. All generation happens locally after the initial weight
download. The heavyweight pipeline is loaded once and reused across card variants.
"""
from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps

DEFAULT_MODEL = "black-forest-labs/FLUX.2-klein-4B"  # 4-step distilled, Apache-2.0


def choose_device(torch, requested: str) -> str:
    requested = requested.lower().strip()
    if requested not in {"auto", "cuda", "mps", "cpu"}:
        raise ValueError("Device must be auto, cuda, mps or cpu")
    if requested != "auto":
        if requested == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but no CUDA GPU is available")
        if requested == "mps" and not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
            raise RuntimeError("MPS requested but no Apple Silicon MPS GPU is available")
        return requested
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _dtype_for_device(torch, device: str):
    if device == "cuda":
        return torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    if device == "mps":
        return torch.float16
    return torch.float32


@lru_cache(maxsize=2)
def load_pipeline(model_id: str, device_request: str):
    """Load once for up to three card variants; first use downloads model weights."""
    try:
        import torch
        from diffusers import Flux2KleinPipeline
    except ImportError as exc:
        raise RuntimeError(
            "Missing FLUX dependencies. Run: python -m pip install -r requirements.txt"
        ) from exc

    device = choose_device(torch, device_request)
    if device == "cpu":
        print("WARNING: CPU FLUX.2 Klein generation will be extremely slow and needs substantial system RAM.")

    dtype = _dtype_for_device(torch, device)
    print(f"Loading local FLUX.2 Klein: {model_id} (device={device}, dtype={dtype})")
    pipe = Flux2KleinPipeline.from_pretrained(model_id, torch_dtype=dtype)
    if device == "cuda":
        # Better compatibility with consumer GPUs; trades system RAM for VRAM.
        pipe.enable_model_cpu_offload()
    else:
        pipe.to(device)
    pipe.set_progress_bar_config(disable=False)
    return pipe, device


def pixelize(image: Image.Image, target_size: int = 128, palette_colors: int = 32) -> Image.Image:
    """Create a real 128x128 PNG with discrete, unblurred pixels."""
    image = image.convert("RGB")
    # Crop only the generated illustration, not the camera source.
    image = ImageOps.fit(image, (target_size, target_size), Image.Resampling.LANCZOS)
    image = image.quantize(colors=palette_colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    return image.convert("RGBA")


def normalize_reference(photo_path: Path, side: int = 768) -> Image.Image:
    """Keep the whole object photograph visible instead of cropping it out."""
    with Image.open(photo_path) as photo:
        rgb = photo.convert("RGB")
        return ImageOps.pad(rgb, (side, side), method=Image.Resampling.LANCZOS, color=(22, 19, 17))


def generate_portrait(
    prompt: str,
    out_path: Path,
    photo_path: Path | None = None,
    *,
    model_id: str = DEFAULT_MODEL,
    device: str = "auto",
    width: int = 768,
    height: int = 768,
    steps: int = 4,
    guidance: float = 1.0,
    seed: int | None = None,
    raw_out_path: Path | None = None,
) -> Path:
    """Generate art from the ObjectAnalysis prompt AND optional physical-object photo.

    ``raw_out_path`` additionally keeps the full-resolution image, which the
    exporter downsizes to the 114x94 Act 1 portrait.
    """
    import torch

    if min(width, height) < 256 or width % 16 or height % 16:
        raise ValueError("FLUX width/height must be multiples of 16 and at least 256")
    if photo_path is not None and not photo_path.is_file():
        raise FileNotFoundError(f"Reference photo not found: {photo_path}")
    pipe, actual_device = load_pipeline(model_id, device)
    seed = seed if seed is not None else secrets.randbelow(2**32)
    generator_device = "cuda" if actual_device == "cuda" else "cpu"
    rng = torch.Generator(device=generator_device).manual_seed(seed)

    kwargs = {
        "prompt": prompt,
        "height": height,
        "width": width,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "generator": rng,
    }
    if photo_path is not None:
        kwargs["image"] = normalize_reference(photo_path)

    # The model consumes the original photograph as a reference when available.
    print(f"Generating local FLUX portrait (seed={seed}; photo reference={photo_path is not None})")
    result = pipe(**kwargs)
    if not result.images:
        raise RuntimeError("FLUX.2 Klein returned no image")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    pixelize(result.images[0], 128).save(out_path, format="PNG")
    if raw_out_path is not None:
        result.images[0].save(raw_out_path, format="PNG")
    return out_path
