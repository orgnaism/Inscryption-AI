from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from inscryption_card_generator.pipeline import run_generation


def main():
    parser = argparse.ArgumentParser(description="Generate an Inscryption-style card from ObjectAnalysis JSON.")
    parser.add_argument("--analysis", type=Path, help="Path to ObjectAnalysis JSON.")
    parser.add_argument("--photo", type=Path, default=None, help="Optional source photo for image-edit generation.")
    parser.add_argument("--variants", type=int, default=1, choices=[1, 2, 3], help="Number of card choices to generate.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Where to write outputs.")
    parser.add_argument("--project-root", type=Path, default=None, help="Path to the original Inscryption-AI-main folder.")
    parser.add_argument("--camera", action="store_true", help="Use the original camera.py from the project root.")
    parser.add_argument("--analyze-photo", action="store_true", help="Use the original analyzer.py on the captured/provided photo.")
    parser.add_argument("--dry-run", action="store_true", help="Skip FLUX and create placeholder portrait/card only.")
    parser.add_argument("--device", choices=["auto", "cuda", "mps", "cpu"], default=None, help="Device for local FLUX.2 Klein 4B.")
    args = parser.parse_args()

    root = args.project_root
    if args.camera:
        if root is None:
            raise SystemExit("--camera requires --project-root pointing to the original Inscryption-AI-main folder")
        import importlib.util, sys
        camera_path = root / "camera.py"
        spec = importlib.util.spec_from_file_location("orig_camera", camera_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("orig_camera", mod)
        spec.loader.exec_module(mod)
        image_path = mod.capture_object()
        if image_path is None:
            raise SystemExit("Camera capture cancelled")
        args.photo = Path(image_path)

    if args.analyze_photo:
        if root is None:
            raise SystemExit("--analyze-photo requires --project-root pointing to the original Inscryption-AI-main folder")
        if args.photo is None:
            raise SystemExit("--analyze-photo requires --photo or --camera")
        import importlib.util, sys
        analyzer_path = root / "analyzer.py"
        spec = importlib.util.spec_from_file_location("orig_analyzer", analyzer_path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("orig_analyzer", mod)
        spec.loader.exec_module(mod)
        data = mod.analyze_object(str(args.photo))
        if args.output_dir is None:
            run_dir = Path("outputs") / f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        else:
            run_dir = args.output_dir
        run_dir.mkdir(parents=True, exist_ok=True)
        analysis_path = run_dir / "object_analysis.json"
        analysis_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        args.analysis = analysis_path
    elif args.analysis is None:
        raise SystemExit("Provide --analysis JSON or use --analyze-photo")

    run_dir = args.output_dir or args.analysis.parent / f"cards_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    for idx in range(args.variants):
        variant_dir = run_dir / f"variant_{idx+1}"
        manifest.append(run_generation(
            analysis_path=args.analysis,
            output_dir=variant_dir,
            photo_path=args.photo,
            variant=idx,
            use_flux=not args.dry_run,
            device=args.device,
            project_root=root,
        ))

    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"variants": manifest}, indent=2), encoding="utf-8")
    print(manifest_path.resolve())


if __name__ == "__main__":
    main()
