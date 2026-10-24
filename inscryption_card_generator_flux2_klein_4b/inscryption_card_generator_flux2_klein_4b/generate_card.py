from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

from inscryption_card_generator.analysis import AnalysisValidationError, normalize_analysis
from inscryption_card_generator.balance import CardValidationError
from inscryption_card_generator.config import balance_rules
from inscryption_card_generator.export import DuplicateCardIdError, PLUGIN_FOLDER
from inscryption_card_generator.pipeline import run_generation
from inscryption_card_generator.taxonomy import identify_subject

DEFAULT_ROOT = Path(__file__).resolve().parents[2]


def _load_root_module(root: Path, name: str):
    """Import the original camera.py / analyzer.py from the scanner project, unmodified in use."""
    path = root / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"orig_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(f"orig_{name}", mod)
    spec.loader.exec_module(mod)
    return mod


def _rescan_reason(data: dict) -> str | None:
    """Why a scan should be retaken before generating a card (None = good enough)."""
    try:
        analysis = normalize_analysis(data)
    except AnalysisValidationError as exc:
        return str(exc)
    ident = identify_subject(analysis)
    if not ident.supported:
        return "; ".join(ident.reasons)
    if balance_rules()["confidence"][analysis.effective_confidence].get("rescan_recommended"):
        return f"confidence is {analysis.effective_confidence} ({analysis.object_name!r})"
    return None


def main():
    parser = argparse.ArgumentParser(description="Generate balanced Inscryption Act 1 cards from ObjectAnalysis JSON.")
    parser.add_argument("--analysis", type=Path, help="Path to ObjectAnalysis JSON.")
    parser.add_argument("--photo", type=Path, default=None, help="Optional source photo for image-edit generation.")
    parser.add_argument("--variants", type=int, default=1, choices=[1, 2, 3], help="Number of card choices to generate.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Where to write outputs.")
    parser.add_argument("--project-root", type=Path, default=None,
                        help="Folder with the original camera.py/analyzer.py (default: this repository's root).")
    parser.add_argument("--camera", action="store_true", help="Use the original camera.py from the project root.")
    parser.add_argument("--analyze-photo", action="store_true", help="Use the original analyzer.py on the captured/provided photo.")
    parser.add_argument("--rescan-attempts", type=int, default=2,
                        help="With --camera: how many times to retake a low-confidence or unusable scan.")
    parser.add_argument("--dry-run", action="store_true", help="Skip FLUX and create placeholder portrait/card only.")
    parser.add_argument("--device", choices=["auto", "cuda", "mps", "cpu"], default=None, help="Device for local FLUX.2 Klein 4B.")
    parser.add_argument("--export-dir", type=Path, default=None,
                        help=f"Mod cards folder to export into, e.g. <Inscryption>/BepInEx/plugins/{PLUGIN_FOLDER}/cards "
                             f"(default: <run folder>/mod_export/{PLUGIN_FOLDER}/cards).")
    parser.add_argument("--no-export", action="store_true", help="Do not write mod files.")
    parser.add_argument("--jsonloader-dir", type=Path, default=None,
                        help="Also write a JSONLoader .jldr2 card here (alternative to the companion plugin; do not install both).")
    parser.add_argument("--overwrite", action="store_true", help="Replace an exported card that has the same id but different content.")
    parser.add_argument("--strict", action="store_true", help="Fail instead of falling back to a conservative card.")
    parser.add_argument("--ai-propose", action="store_true",
                        help="Let the Ollama model propose name/flavor/stats/sigils; the rules still validate everything.")
    parser.add_argument("--explain", action="store_true", help="Print how each JSON property was interpreted.")
    args = parser.parse_args()

    root = args.project_root or (DEFAULT_ROOT if (DEFAULT_ROOT / "analyzer.py").exists() else None)
    if (args.camera or args.analyze_photo) and root is None:
        raise SystemExit("--camera/--analyze-photo need --project-root pointing to the folder with camera.py and analyzer.py")

    # As before: --camera with --analysis only captures a reference photo for the artwork.
    need_analysis = args.analyze_photo or (args.camera and args.analysis is None)
    if args.camera and not need_analysis:
        image_path = _load_root_module(root, "camera").capture_object()
        if image_path is None:
            raise SystemExit("Camera capture cancelled")
        args.photo = Path(image_path)

    if need_analysis:
        camera = _load_root_module(root, "camera") if args.camera else None
        analyzer = _load_root_module(root, "analyzer")
        attempts = args.rescan_attempts + 1 if args.camera else 1
        data = None
        for attempt in range(1, attempts + 1):
            if camera is not None:
                image_path = camera.capture_object()
                if image_path is None:
                    raise SystemExit("Camera capture cancelled")
                args.photo = Path(image_path)
            if args.photo is None:
                raise SystemExit("--analyze-photo requires --photo or --camera")
            try:
                data = analyzer.analyze_object(str(args.photo))
            except Exception as exc:  # analyzer.AnalysisError, connection problems
                print(f"Image analysis failed: {exc}")
                data = None
                reason = "analysis failed"
            else:
                reason = _rescan_reason(data)
            if reason is None:
                break
            if attempt < attempts:
                print(f"Please rescan ({reason}). Attempt {attempt + 1} of {attempts}.")
            elif data is None:
                raise SystemExit("Image analysis failed; no card generated.")
            else:
                print(f"Scan still unreliable ({reason}); generating a conservative card.")
        run_dir = args.output_dir or Path("outputs") / f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        run_dir.mkdir(parents=True, exist_ok=True)
        analysis_path = run_dir / "object_analysis.json"
        analysis_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        args.analysis = analysis_path
    elif args.analysis is None:
        raise SystemExit("Provide --analysis JSON or use --analyze-photo / --camera")

    run_dir = args.output_dir or args.analysis.parent / f"cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)
    export_dir = None if args.no_export else (args.export_dir or run_dir / "mod_export" / PLUGIN_FOLDER / "cards")

    manifest = []
    for idx in range(args.variants):
        try:
            entry = run_generation(
                analysis_path=args.analysis,
                output_dir=run_dir / f"variant_{idx+1}",
                photo_path=args.photo,
                variant=idx,
                use_flux=not args.dry_run,
                device=args.device,
                project_root=root,
                export_dir=export_dir,
                jsonloader_dir=args.jsonloader_dir,
                strict=args.strict,
                use_ai=args.ai_propose,
                overwrite=args.overwrite,
            )
        except AnalysisValidationError as exc:
            raise SystemExit(f"Unusable analysis JSON: {exc}")
        except (CardValidationError, DuplicateCardIdError) as exc:
            raise SystemExit(f"Card not generated: {exc}")
        manifest.append(entry)
        card = json.loads(Path(entry["card_data"]).read_text(encoding="utf-8"))
        sigils = ", ".join(s["display_name"] for s in card["sigils"]) or "no sigils"
        cost = "-" if card["blood_cost"] is None else card["blood_cost"]
        print(f"[variant {idx+1}] {card['display_name']} | {card['tribe']} | {card['attack']}/{card['health']} | "
              f"{cost} blood | {sigils} | {card['validation_status']}"
              + (" | RESCAN RECOMMENDED" if card["rescan_recommended"] else ""))
        for line in card["validation"]["adjustments"] + card["validation"]["errors"]:
            print(f"    - {line}")
        if args.explain and card["diagnostics"].get("physical_profile"):
            for field, text in card["diagnostics"]["physical_profile"]["interpretation"].items():
                print(f"    {field}: {text}")
            for line in card["diagnostics"]["stat_estimate"]["trace"]:
                print(f"    stats: {line}")

    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"variants": manifest, "export_dir": str(export_dir) if export_dir else None},
                                        indent=2), encoding="utf-8")
    print(manifest_path.resolve())
    if export_dir is not None:
        print(f"Mod files: {export_dir.resolve()}")
    if not any(m.get("mod_export") or m.get("act1_portrait") for m in manifest):
        sys.exit(2)


if __name__ == "__main__":
    main()
