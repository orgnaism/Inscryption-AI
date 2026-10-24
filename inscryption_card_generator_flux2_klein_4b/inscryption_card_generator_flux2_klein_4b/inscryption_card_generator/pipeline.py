"""Unchanged JSON/stat/card-rendering pipeline with local FLUX artwork backend."""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .art_api import make_placeholder_portrait
from .flux_local import generate_portrait
from .prompts import make_portrait_prompt
from .renderer import render_card
from .rules import generate_card_data
from .schema_compat import parse_analysis


def run_generation(
    analysis_path: Path,
    output_dir: Path,
    photo_path: Path | None = None,
    variant: int = 0,
    use_flux: bool = True,
    project_root: Path | None = None,
    device: str | None = None,
):
    load_dotenv()
    output_dir.mkdir(parents=True, exist_ok=True)
    obj = parse_analysis(analysis_path.read_text(encoding="utf-8"), project_root=project_root)
    card = generate_card_data(obj, variant=variant)
    prompt = make_portrait_prompt(obj, card)

    prompt_path = output_dir / f"variant_{variant+1}_prompt.txt"
    portrait_path = output_dir / f"variant_{variant+1}_portrait_128.png"
    full_card_path = output_dir / f"variant_{variant+1}_full_card.png"
    card_json_path = output_dir / f"variant_{variant+1}_card_data.json"
    prompt_path.write_text(prompt, encoding="utf-8")

    if use_flux:
        generate_portrait(
            prompt=prompt,
            out_path=portrait_path,
            photo_path=photo_path,
            model_id=os.getenv("FLUX_MODEL_ID", "black-forest-labs/FLUX.2-klein-4B"),
            device=device or os.getenv("FLUX_DEVICE", "auto"),
            width=int(os.getenv("FLUX_WIDTH", "768")),
            height=int(os.getenv("FLUX_HEIGHT", "768")),
            steps=int(os.getenv("FLUX_STEPS", "4")),
            guidance=float(os.getenv("FLUX_GUIDANCE", "1.0")),
        )
    else:
        make_placeholder_portrait(portrait_path, card.name)

    render_card(card, portrait_path, full_card_path)

    card.portrait_path = str(portrait_path.resolve())
    card.full_card_path = str(full_card_path.resolve())
    card.prompt_path = str(prompt_path.resolve())
    card_json_path.write_text(json.dumps(card.to_dict(), indent=2), encoding="utf-8")
    return {
        "analysis": str(analysis_path.resolve()),
        "photo": str(photo_path.resolve()) if photo_path else None,
        "card_data": str(card_json_path.resolve()),
        "portrait": str(portrait_path.resolve()),
        "full_card": str(full_card_path.resolve()),
        "prompt": str(prompt_path.resolve()),
    }
