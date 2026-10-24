"""End-to-end generation for one card variant: JSON -> balanced card -> art -> export.

Same entry point and outputs as before (prompt, 128px portrait, full card PNG,
card JSON), plus the 114x94 Act 1 portrait, the mod export and a registration
preview. Image analysis (camera.py / analyzer.py) is unchanged upstream of this.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from .analysis import normalize_analysis
from .art_api import make_placeholder_portrait
from .artwork import make_act1_portrait
from .export import export_card, export_jsonloader, registration_snippet
from .flux_local import generate_portrait
from .generator import design_card
from .prompts import make_portrait_prompt
from .renderer import render_card
from .schema_compat import parse_analysis


def strict_schema_check(json_text: str, project_root: Path | None) -> str | None:
    """Validate against the original pydantic ObjectAnalysis schema; None means it passed."""
    try:
        parse_analysis(json_text, project_root=project_root)
        return None
    except Exception as exc:  # pydantic.ValidationError or JSON errors
        return f"{type(exc).__name__}: {str(exc).splitlines()[0]}"


def run_generation(
    analysis_path: Path,
    output_dir: Path,
    photo_path: Path | None = None,
    variant: int = 0,
    use_flux: bool = True,
    project_root: Path | None = None,
    device: str | None = None,
    export_dir: Path | None = None,
    jsonloader_dir: Path | None = None,
    strict: bool = False,
    use_ai: bool = False,
    overwrite: bool = False,
):
    load_dotenv()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_text = analysis_path.read_text(encoding="utf-8")
    card = design_card(json_text, variant=variant, strict=strict, use_ai=use_ai)
    card.diagnostics["strict_schema"] = strict_schema_check(json_text, project_root) or "passed"

    prefix = f"variant_{variant+1}"
    prompt_path = output_dir / f"{prefix}_prompt.txt"
    portrait_path = output_dir / f"{prefix}_portrait_128.png"
    raw_art_path = output_dir / f"{prefix}_art_raw.png"
    act1_path = output_dir / f"{prefix}_portrait_114x94.png"
    full_card_path = output_dir / f"{prefix}_full_card.png"
    card_json_path = output_dir / f"{prefix}_card_data.json"
    snippet_path = output_dir / f"{prefix}_registration.cs.txt"
    manifest = {
        "analysis": str(analysis_path.resolve()),
        "photo": str(photo_path.resolve()) if photo_path else None,
        "card_id": card.card_id,
        "display_name": card.display_name,
        "validation_status": card.validation_status,
        "rescan_recommended": card.rescan_recommended,
        "card_data": str(card_json_path.resolve()),
    }

    if not card.exportable:
        card_json_path.write_text(json.dumps(card.to_dict(), indent=2), encoding="utf-8")
        return manifest

    prompt = make_portrait_prompt(normalize_analysis(json_text), card)
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
            raw_out_path=raw_art_path,
        )
        art_source = raw_art_path
    else:
        make_placeholder_portrait(portrait_path, card.name, creature=card.subject_kind == "animal")
        art_source = portrait_path
    make_act1_portrait(art_source, act1_path)
    render_card(card, portrait_path, full_card_path)

    card.artwork_reference = {
        "act1_portrait_114x94": str(act1_path.resolve()),
        "preview_portrait_128": str(portrait_path.resolve()),
        "full_card_preview": str(full_card_path.resolve()),
        "prompt": str(prompt_path.resolve()),
        "generated_by": "FLUX.2 Klein (local)" if use_flux else "placeholder (dry run)",
    }
    snippet_path.write_text(registration_snippet(card), encoding="utf-8")
    manifest.update({
        "portrait": str(portrait_path.resolve()),
        "act1_portrait": str(act1_path.resolve()),
        "full_card": str(full_card_path.resolve()),
        "prompt": str(prompt_path.resolve()),
        "registration_preview": str(snippet_path.resolve()),
    })
    if export_dir is not None:
        manifest["mod_export"] = export_card(card, act1_path, export_dir, overwrite=overwrite)
    if jsonloader_dir is not None:
        manifest["jsonloader_export"] = export_jsonloader(card, act1_path, jsonloader_dir)

    card_json_path.write_text(json.dumps(card.to_dict(), indent=2), encoding="utf-8")
    return manifest
