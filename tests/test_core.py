import json
from pathlib import Path

from whisper_batch_core import (
    DEFAULT_MODEL_NAME,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_TASK_NAME,
    SUPPORTED_MODELS,
    SUPPORTED_OUTPUT_FORMATS,
    SUPPORTED_TASKS,
    build_output_metadata_path,
    get_model_cache_dir,
    is_model_cached,
    resolve_output_metadata_path,
    should_skip_output_due_to_metadata,
)


def test_core_defaults_and_supported_lists_are_complete():
    assert DEFAULT_MODEL_NAME in SUPPORTED_MODELS
    assert DEFAULT_MODEL_NAME == "large-v3"
    assert DEFAULT_OUTPUT_FORMAT == "txt"
    assert DEFAULT_TASK_NAME == "transcribe"
    assert "json" in SUPPORTED_OUTPUT_FORMATS
    assert "translate" in SUPPORTED_TASKS


def test_get_model_cache_dir_prefers_hf_home(monkeypatch, tmp_path):
    hf_home = tmp_path / "hf_home"
    monkeypatch.setenv("HF_HOME", str(hf_home))
    assert get_model_cache_dir("base") == hf_home / "hub" / "models--Systran--faster-whisper-base"


def test_get_model_cache_dir_falls_back_to_hf_cache_then_xdg(monkeypatch, tmp_path):
    fallback_cache = tmp_path / "hf_cache"
    xdg_cache = tmp_path / "xdg_cache"
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", str(fallback_cache))
    assert get_model_cache_dir("tiny") == fallback_cache / "models--Systran--faster-whisper-tiny"

    monkeypatch.delenv("HUGGINGFACE_HUB_CACHE", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_cache))
    assert (
        get_model_cache_dir("tiny")
        == xdg_cache / "huggingface" / "hub" / "models--Systran--faster-whisper-tiny"
    )


def test_metadata_path_helpers_add_suffix():
    output_file = Path("/tmp/example.txt")
    assert build_output_metadata_path(output_file) == Path("/tmp/example.txt.metadata.json")
    assert resolve_output_metadata_path(output_file) == Path("/tmp/example.txt.metadata.json")


def test_is_model_cached_uses_directory_semantics(tmp_path):
    assert not is_model_cached("base", cache_dir=str(tmp_path))
    (tmp_path / "models--Systran--faster-whisper-base").mkdir(parents=True)
    assert is_model_cached("base", cache_dir=str(tmp_path))


def test_should_skip_output_due_to_metadata_validates_match_and_change(tmp_path):
    metadata_path = tmp_path / "output.txt.metadata.json"
    payload = {
        "source_path": "/media/input.wav",
        "output_path": "/media/output.txt",
        "model": "base",
        "include_timestamps": False,
        "output_format": "txt",
        "task": "transcribe",
    }
    metadata_path.write_text(json.dumps(payload), encoding="utf-8")

    assert should_skip_output_due_to_metadata(
        source_path="/media/input.wav",
        output_path="/media/output.txt",
        metadata_path=metadata_path,
        model_name="base",
        include_timestamps=False,
        output_format="txt",
        task="transcribe",
    )

    assert not should_skip_output_due_to_metadata(
        source_path="/media/input.wav",
        output_path="/media/output.txt",
        metadata_path=metadata_path,
        model_name="small",
        include_timestamps=False,
        output_format="txt",
        task="transcribe",
    )

    assert not should_skip_output_due_to_metadata(
        source_path="/media/input.wav",
        output_path="/media/output.txt",
        metadata_path=metadata_path,
        model_name="base",
        include_timestamps=True,
        output_format="txt",
        task="transcribe",
    )

    assert not should_skip_output_due_to_metadata(
        source_path="/media/input.wav",
        output_path="/media/output.txt",
        metadata_path=tmp_path / "missing.json",
        model_name="base",
        include_timestamps=False,
        output_format="txt",
        task="transcribe",
    )
