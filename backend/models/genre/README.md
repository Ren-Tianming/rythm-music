# Tonnetz ONNX genre adapter

This directory is the runtime mount point for the trained genre model from the earlier music-analysis project. Model binaries are intentionally ignored by Git.

## Required files

1. `genre-model.onnx`
2. `genre-model.metadata.json`

The ONNX graph must accept one `float32` input with shape `[batch, 12]` (or
`[12]`) and return one vector whose length equals the number of labels. The
feature order is:

```text
[six Tonnetz means, six Tonnetz standard deviations]
```

Export the training-time scaler into the ONNX graph whenever possible. If the
graph does not contain it, add 12-value `feature_mean` and `feature_scale`
arrays to the metadata. Set `output_type` to `logits` or `probabilities`, and
keep `labels` in the exact class order used during training.

Set these values when running in Docker:

```dotenv
AUDIO_GENRE_MODEL_PATH=/app/models/genre/genre-model.onnx
AUDIO_GENRE_MODEL_METADATA_PATH=/app/models/genre/genre-model.metadata.json
```

The older safe `.npz` 128/64/32 adapter remains supported for migration, but
ONNX is the default and recommended runtime.

Do not commit trained weights if their dataset or license prohibits redistribution.
