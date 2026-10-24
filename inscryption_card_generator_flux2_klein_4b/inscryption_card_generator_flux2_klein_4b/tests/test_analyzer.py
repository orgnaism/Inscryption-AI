"""The original scanner's analyzer.py with a fake Ollama client (no model, no network)."""
import importlib.util
import json
import sys
from types import SimpleNamespace

import pytest

from conftest import PINECONE, REPO_ROOT


@pytest.fixture
def analyzer(monkeypatch):
    """Import repo-root analyzer.py with `ollama` replaced by a stub whose chat() we control."""
    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(chat=None))
    spec = importlib.util.spec_from_file_location("scanner_analyzer", REPO_ROOT / "analyzer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def replying(text, calls=None):
    def chat(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        return {"message": {"content": text}}
    return chat


def test_analysis_success_with_fenced_output(analyzer):
    calls = []
    analyzer.ollama.chat = replying("```json\n" + json.dumps(PINECONE) + "\n```", calls)
    assert analyzer.analyze_object("photo.jpg") == PINECONE
    assert calls[0]["format"] == "json" and calls[0]["messages"][0]["images"] == ["photo.jpg"]
    assert "visible_features" in calls[0]["messages"][0]["content"]


def test_prose_around_json_is_tolerated(analyzer):
    analyzer.ollama.chat = replying("Sure! " + json.dumps(PINECONE) + " Hope that helps.")
    assert analyzer.analyze_object("photo.jpg")["object_name"] == "pinecone"


@pytest.mark.parametrize("text", ["I cannot see an object.", "{not valid json}", "[1, 2, 3]"])
def test_unusable_model_output_raises_analysis_error(analyzer, text):
    analyzer.ollama.chat = replying(text)
    with pytest.raises(analyzer.AnalysisError):
        analyzer.analyze_object("photo.jpg")


def test_failed_request_raises_analysis_error(analyzer):
    def down(**kwargs):
        raise ConnectionError("connection refused")

    analyzer.ollama.chat = down
    with pytest.raises(analyzer.AnalysisError, match="Is Ollama running"):
        analyzer.analyze_object("photo.jpg")
