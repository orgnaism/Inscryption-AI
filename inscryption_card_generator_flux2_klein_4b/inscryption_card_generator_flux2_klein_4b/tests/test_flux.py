"""Mock local FLUX inference to validate code paths without model download/GPU."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from inscryption_card_generator import flux_local


def test_pixelize_is_exact_128():
    result = flux_local.pixelize(Image.new("RGB", (512, 650), (100, 80, 52)))
    assert result.size == (128, 128)
    assert result.mode == "RGBA"


def test_reference_keeps_input_in_frame():
    with tempfile.TemporaryDirectory() as tmp:
        photo = Path(tmp) / "photo.png"
        Image.new("RGB", (400, 600), (100, 80, 50)).save(photo)
        result = flux_local.normalize_reference(photo)
        assert result.size == (768, 768)
        assert result.mode == "RGB"


def test_flux_call_passes_prompt_and_camera_photo(monkeypatch):
    captured = []

    class FakePipe:
        def __call__(self, **kwargs):
            captured.append(kwargs)
            return SimpleNamespace(images=[Image.new("RGB", (600, 600), (80, 70, 60))])

    class FakeGenerator:
        def __init__(self, device):
            self.device = device
        def manual_seed(self, seed):
            return self

    monkeypatch.setattr(flux_local, "load_pipeline", lambda *args: (FakePipe(), "cpu"))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(Generator=FakeGenerator))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        photo = tmp / "photo.png"
        result = tmp / "portrait_128.png"
        Image.new("RGB", (640, 480), "brown").save(photo)
        flux_local.generate_portrait("Make a pinecone monster", result, photo_path=photo, seed=123)
        assert result.is_file()
        assert Image.open(result).size == (128, 128)
        assert captured[0]["prompt"] == "Make a pinecone monster"
        assert captured[0]["image"].size == (768, 768)
        assert captured[0]["num_inference_steps"] == 4


def test_flux_raw_output_is_kept_for_the_act1_portrait(monkeypatch):
    class FakePipe:
        def __call__(self, **kwargs):
            return SimpleNamespace(images=[Image.new("RGB", (768, 768), (80, 70, 60))])

    class FakeGenerator:
        def __init__(self, device):
            pass
        def manual_seed(self, seed):
            return self

    monkeypatch.setattr(flux_local, "load_pipeline", lambda *args: (FakePipe(), "cpu"))
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(Generator=FakeGenerator))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        flux_local.generate_portrait("A raven", tmp / "p128.png", seed=1, raw_out_path=tmp / "raw.png")
        assert Image.open(tmp / "raw.png").size == (768, 768)
        assert Image.open(tmp / "p128.png").size == (128, 128)
