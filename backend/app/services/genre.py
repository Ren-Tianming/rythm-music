import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import librosa
import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenreResult:
    genre: str | None
    confidence: float | None
    status: str
    model_version: str | None = None


def extract_tonnetz_features(y: np.ndarray, sample_rate: int) -> np.ndarray:
    """Extract the 12-value Tonnetz vector used by the legacy DNN adapter."""
    harmonic = librosa.effects.harmonic(y)
    tonnetz = librosa.feature.tonnetz(y=harmonic, sr=sample_rate)
    result = np.concatenate((np.mean(tonnetz, axis=1), np.std(tonnetz, axis=1))).astype(np.float32)
    return cast(np.ndarray, result)


def _softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values)
    exponentials = np.exp(shifted)
    return cast(np.ndarray, exponentials / np.sum(exponentials))


def _load_metadata(path: Path | None) -> dict[str, object]:
    if path is None or not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("genre model metadata must be a JSON object")
    return cast(dict[str, object], payload)


def _labels(metadata: dict[str, object]) -> list[str]:
    labels = metadata.get("labels", metadata.get("classes"))
    if not isinstance(labels, list) or not labels or not all(isinstance(label, str) for label in labels):
        raise ValueError("genre model metadata must contain ordered string labels")
    return cast(list[str], labels)


def _validate_feature_schema(metadata: dict[str, object], features: np.ndarray) -> None:
    if metadata.get("feature_schema", "tonnetz_mean_std_v1") != "tonnetz_mean_std_v1":
        raise ValueError("unsupported genre feature schema")
    if features.shape != (12,):
        raise ValueError("tonnetz_mean_std_v1 must contain exactly 12 values")


def _metadata_normalize(features: np.ndarray, metadata: dict[str, object]) -> np.ndarray:
    """Apply optional training-time standardization stored in metadata.

    Prefer exporting normalization as part of the ONNX graph. This fallback is
    useful when the original model was exported without its scaler.
    """
    mean = metadata.get("feature_mean")
    scale = metadata.get("feature_scale")
    if mean is None and scale is None:
        return features
    if not isinstance(mean, list) or not isinstance(scale, list):
        raise ValueError("feature_mean and feature_scale must both be arrays")
    mean_array = np.asarray(mean, dtype=np.float32)
    scale_array = np.asarray(scale, dtype=np.float32)
    if mean_array.shape != (12,) or scale_array.shape != (12,):
        raise ValueError("feature normalization arrays must have shape (12,)")
    safe_scale = np.where(scale_array == 0, 1.0, scale_array)
    return cast(np.ndarray, (features - mean_array) / safe_scale)


def _predict_npz(model_path: Path, metadata: dict[str, object], features: np.ndarray) -> GenreResult:
    labels = _labels(metadata)
    _validate_feature_schema(metadata, features)

    if metadata.get("hidden_layers", [128, 64, 32]) != [128, 64, 32]:
        raise ValueError("the legacy genre network must use 128/64/32 hidden layers")
    hidden_layers = [128, 64, 32]
    hidden_activation = metadata.get("hidden_activation", "tanh")
    if hidden_activation not in {"tanh", "relu"}:
        raise ValueError("unsupported genre hidden activation")

    with np.load(model_path, allow_pickle=False) as weights:
        x = features.reshape(1, -1)
        if "scaler_mean" in weights and "scaler_scale" in weights:
            scale = np.where(weights["scaler_scale"] == 0, 1.0, weights["scaler_scale"])
            x = (x - weights["scaler_mean"]) / scale
        expected_sizes = [features.size, *hidden_layers, len(labels)]
        layer = 0
        while f"W{layer}" in weights and f"b{layer}" in weights:
            expected_shape = (expected_sizes[layer], expected_sizes[layer + 1])
            if weights[f"W{layer}"].shape != expected_shape:
                raise ValueError(f"W{layer} must have shape {expected_shape}")
            x = x @ weights[f"W{layer}"] + weights[f"b{layer}"]
            if f"W{layer + 1}" in weights:
                x = np.tanh(x) if hidden_activation == "tanh" else np.maximum(x, 0)
            layer += 1
        if layer != len(expected_sizes) - 1 or x.shape[1] != len(labels):
            raise ValueError("genre model weights do not match metadata")

    probabilities = _softmax(x[0])
    best = int(np.argmax(probabilities))
    return GenreResult(
        genre=labels[best],
        confidence=round(float(probabilities[best]), 5),
        status="READY",
        model_version=str(metadata.get("model_version", model_path.stem)),
    )


def _predict_onnx(model_path: Path, metadata: dict[str, object], features: np.ndarray) -> GenreResult:
    """Run the legacy Tonnetz classifier through ONNX Runtime on CPU."""
    import onnxruntime as ort

    labels = _labels(metadata)
    _validate_feature_schema(metadata, features)
    normalized = _metadata_normalize(features, metadata).astype(np.float32, copy=False)

    session_options = ort.SessionOptions()
    session_options.intra_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path),
        sess_options=session_options,
        providers=["CPUExecutionProvider"],
    )
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    if len(inputs) != 1 or not outputs:
        raise ValueError("genre ONNX model must expose one input and at least one output")

    input_name = str(metadata.get("input_name") or inputs[0].name)
    output_name = str(metadata.get("output_name") or outputs[0].name)
    input_shape: list[Any] = list(inputs[0].shape)
    if len(input_shape) == 1:
        model_input = normalized
    elif len(input_shape) == 2:
        model_input = normalized.reshape(1, 12)
    else:
        raise ValueError("genre ONNX input must have shape [12] or [batch, 12]")

    raw_output = np.asarray(session.run([output_name], {input_name: model_input})[0], dtype=np.float32)
    scores = raw_output.reshape(-1)
    if scores.size != len(labels):
        raise ValueError("genre ONNX output size does not match metadata labels")

    output_type = str(metadata.get("output_type", "logits")).lower()
    if output_type == "probabilities":
        total = float(np.sum(scores))
        if np.any(scores < 0) or total <= 0:
            raise ValueError("probability output must be non-negative with a positive sum")
        probabilities = scores / total
    elif output_type == "logits":
        probabilities = _softmax(scores)
    else:
        raise ValueError("output_type must be logits or probabilities")

    best = int(np.argmax(probabilities))
    return GenreResult(
        genre=labels[best],
        confidence=round(float(probabilities[best]), 5),
        status="READY",
        model_version=str(metadata.get("model_version", model_path.stem)),
    )


def extract_logmel_segments(y: np.ndarray, sample_rate: int, metadata: dict[str, object]) -> np.ndarray:
    """Reproduce the preprocessing used to train the bundled GTZAN Log-Mel CNN."""
    preprocessing = metadata.get("preprocessing")
    if not isinstance(preprocessing, dict):
        raise ValueError("logmel model metadata must contain preprocessing settings")

    target_rate = int(preprocessing.get("sample_rate", 22050))
    segment_seconds = float(preprocessing.get("segment_seconds", 3.0))
    segment_count = int(preprocessing.get("segments_per_track", 10))
    n_fft = int(preprocessing.get("n_fft", 2048))
    hop_length = int(preprocessing.get("hop_length", 512))
    n_mels = int(preprocessing.get("n_mels", 64))
    fmin = float(preprocessing.get("fmin", 20.0))
    fmax = float(preprocessing.get("fmax", target_rate / 2))
    top_db = float(preprocessing.get("top_db", 80.0))
    if target_rate <= 0 or segment_seconds <= 0 or segment_count <= 0 or top_db <= 0:
        raise ValueError("invalid logmel preprocessing settings")

    mono = np.asarray(y, dtype=np.float32)
    if sample_rate != target_rate:
        mono = librosa.resample(mono, orig_sr=sample_rate, target_sr=target_rate)
    segment_samples = int(round(target_rate * segment_seconds))
    if mono.size < segment_samples:
        mono = np.pad(mono, (0, segment_samples - mono.size))
    max_start = max(0, mono.size - segment_samples)
    starts = np.linspace(0, max_start, num=segment_count, dtype=np.int64)

    segments: list[np.ndarray] = []
    for start in starts:
        clip = mono[int(start) : int(start) + segment_samples]
        mel = librosa.feature.melspectrogram(
            y=clip,
            sr=target_rate,
            n_fft=n_fft,
            hop_length=hop_length,
            n_mels=n_mels,
            fmin=fmin,
            fmax=fmax,
            power=2.0,
        )
        logmel = librosa.power_to_db(mel, ref=np.max, top_db=top_db)
        normalized = np.clip((logmel + top_db) / top_db, 0.0, 1.0).astype(np.float32)
        segments.append(normalized[np.newaxis, :, :])
    return np.stack(segments)


def _predict_logmel_onnx(
    model_path: Path,
    metadata: dict[str, object],
    y: np.ndarray,
    sample_rate: int,
) -> GenreResult:
    import onnxruntime as ort

    labels = _labels(metadata)
    model_input = extract_logmel_segments(y, sample_rate, metadata)
    session_options = ort.SessionOptions()
    session_options.intra_op_num_threads = 1
    session = ort.InferenceSession(
        str(model_path),
        sess_options=session_options,
        providers=["CPUExecutionProvider"],
    )
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    if len(inputs) != 1 or not outputs:
        raise ValueError("genre ONNX model must expose one input and at least one output")
    input_meta = metadata.get("input")
    output_meta = metadata.get("output")
    input_name = (
        str(input_meta.get("name"))
        if isinstance(input_meta, dict) and input_meta.get("name")
        else inputs[0].name
    )
    output_name = (
        str(output_meta.get("name"))
        if isinstance(output_meta, dict) and output_meta.get("name")
        else outputs[0].name
    )
    raw = np.asarray(session.run([output_name], {input_name: model_input})[0], dtype=np.float32)
    if raw.ndim != 2 or raw.shape != (model_input.shape[0], len(labels)):
        raise ValueError("logmel ONNX output must have shape [segment, class]")
    if np.any(raw < 0) or not np.all(np.isfinite(raw)):
        raise ValueError("logmel probability output contains invalid values")
    totals = raw.sum(axis=1, keepdims=True)
    if np.any(totals <= 0):
        raise ValueError("logmel probability rows must have a positive sum")
    probabilities = np.mean(raw / totals, axis=0)
    best = int(np.argmax(probabilities))
    return GenreResult(
        genre=labels[best],
        confidence=round(float(probabilities[best]), 5),
        status="READY",
        model_version=str(metadata.get("model_version", model_path.stem)),
    )


def predict_genre(y: np.ndarray, sample_rate: int) -> GenreResult:
    """Run the configured genre classifier using its declared feature schema."""
    settings = get_settings()
    model_path = settings.genre_model_path
    if model_path is None or not model_path.is_file():
        return GenreResult(None, None, "NOT_CONFIGURED")
    try:
        metadata = _load_metadata(settings.genre_model_metadata_path)
        suffix = model_path.suffix.lower()
        if metadata.get("model_type") == "logmel_cnn":
            if suffix != ".onnx":
                raise ValueError("logmel_cnn requires an ONNX model")
            return _predict_logmel_onnx(model_path, metadata, y, sample_rate)
        features = extract_tonnetz_features(y, sample_rate)
        if suffix == ".onnx":
            return _predict_onnx(model_path, metadata, features)
        if suffix == ".npz":
            return _predict_npz(model_path, metadata, features)
        raise ValueError("genre model must be an ONNX or legacy NPZ file")
    except Exception:
        logger.exception("Genre model loading or inference failed")
        return GenreResult(None, None, "MODEL_ERROR")
