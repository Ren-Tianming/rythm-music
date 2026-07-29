import json
import sys
from types import SimpleNamespace

import numpy as np
from app.services.genre import _predict_logmel_onnx, _predict_npz, _predict_onnx, extract_logmel_segments


def test_safe_npz_genre_adapter(tmp_path) -> None:
    model_path = tmp_path / "genre-model.npz"
    metadata_path = tmp_path / "genre-model.json"
    np.savez(
        model_path,
        W0=np.zeros((12, 128), dtype=np.float32),
        b0=np.zeros(128, dtype=np.float32),
        W1=np.zeros((128, 64), dtype=np.float32),
        b1=np.zeros(64, dtype=np.float32),
        W2=np.zeros((64, 32), dtype=np.float32),
        b2=np.zeros(32, dtype=np.float32),
        W3=np.zeros((32, 2), dtype=np.float32),
        b3=np.array([0.0, 10.0], dtype=np.float32),
    )
    metadata_path.write_text(
        json.dumps(
            {
                "labels": ["ambient", "electronic"],
                "feature_schema": "tonnetz_mean_std_v1",
                "model_version": "legacy-dnn-test",
                "hidden_layers": [128, 64, 32],
                "hidden_activation": "tanh",
            }
        ),
        encoding="utf-8",
    )

    result = _predict_npz(
        model_path,
        json.loads(metadata_path.read_text(encoding="utf-8")),
        np.ones(12, dtype=np.float32),
    )
    assert result.status == "READY"
    assert result.genre == "electronic"
    assert result.confidence is not None and result.confidence > 0.99


def test_onnx_genre_adapter_uses_ordered_labels(tmp_path, monkeypatch) -> None:
    model_path = tmp_path / "genre-model.onnx"
    model_path.write_bytes(b"test-placeholder")
    metadata = {
        "labels": ["ambient", "electronic"],
        "feature_schema": "tonnetz_mean_std_v1",
        "model_version": "onnx-test-v1",
        "output_type": "logits",
    }

    class FakeOptions:
        intra_op_num_threads = 0

    class FakeSession:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def get_inputs(self) -> list[SimpleNamespace]:
            return [SimpleNamespace(name="tonnetz", shape=[None, 12])]

        def get_outputs(self) -> list[SimpleNamespace]:
            return [SimpleNamespace(name="logits")]

        def run(self, _: list[str], feeds: dict[str, np.ndarray]) -> list[np.ndarray]:
            assert feeds["tonnetz"].shape == (1, 12)
            return [np.array([[0.0, 9.0]], dtype=np.float32)]

    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(SessionOptions=FakeOptions, InferenceSession=FakeSession),
    )
    result = _predict_onnx(model_path, metadata, np.ones(12, dtype=np.float32))
    assert result.status == "READY"
    assert result.genre == "electronic"
    assert result.model_version == "onnx-test-v1"
    assert result.confidence is not None and result.confidence > 0.99


def test_bundled_logmel_preprocessing_and_prediction(tmp_path, monkeypatch) -> None:
    metadata = {
        "model_version": "gtzan-test",
        "model_type": "logmel_cnn",
        "classes": ["blues", "rock"],
        "input": {"name": "log_mel"},
        "output": {"name": "probabilities"},
        "preprocessing": {
            "sample_rate": 22050,
            "segment_seconds": 3.0,
            "segments_per_track": 10,
            "n_fft": 2048,
            "hop_length": 512,
            "n_mels": 64,
            "fmin": 20.0,
            "fmax": 11025.0,
            "top_db": 80.0,
        },
    }
    audio = np.sin(2 * np.pi * 220 * np.arange(22050 * 4, dtype=np.float32) / 22050)
    features = extract_logmel_segments(audio, 22050, metadata)
    assert features.shape == (10, 1, 64, 130)
    assert np.all((features >= 0) & (features <= 1))

    class FakeOptions:
        intra_op_num_threads = 0

    class FakeSession:
        def __init__(self, *_: object, **__: object) -> None:
            pass

        def get_inputs(self) -> list[SimpleNamespace]:
            return [SimpleNamespace(name="log_mel", shape=[None, 1, 64, 130])]

        def get_outputs(self) -> list[SimpleNamespace]:
            return [SimpleNamespace(name="probabilities")]

        def run(self, _: list[str], feeds: dict[str, np.ndarray]) -> list[np.ndarray]:
            assert feeds["log_mel"].shape == (10, 1, 64, 130)
            return [np.tile(np.array([[0.1, 0.9]], dtype=np.float32), (10, 1))]

    monkeypatch.setitem(
        sys.modules,
        "onnxruntime",
        SimpleNamespace(SessionOptions=FakeOptions, InferenceSession=FakeSession),
    )
    model_path = tmp_path / "genre-model.onnx"
    model_path.write_bytes(b"test-placeholder")
    result = _predict_logmel_onnx(model_path, metadata, audio, 22050)
    assert result.status == "READY"
    assert result.genre == "rock"
    assert result.confidence == 0.9
