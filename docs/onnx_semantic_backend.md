# Offline ONNX semantic embeddings

EvalGuard's default semantic backend uses Sentence Transformers. In lightweight CI
images or environments where PyTorch is undesirable, install the ONNX extra and
provide an already-downloaded ONNX model plus its matching tokenizer files.

## Install

```bash
pip install "evalguard[onnx]"
```

The extra installs ONNX Runtime and Transformers, but not PyTorch. It does not
download model weights. Keep the model and tokenizer files in a local directory
or provision them as part of your deployment artifact.

## Configure

```python
from evalguard.contamination.semantic import OnnxRuntimeBackend, SemanticDetector

onnx_backend = OnnxRuntimeBackend(
    model_path="models/all-MiniLM-L6-v2/model_quantized.onnx",
    tokenizer_path="models/all-MiniLM-L6-v2",
    max_length=256,
)
detector = SemanticDetector(backend=onnx_backend, similarity_threshold=0.85)

score, is_contaminated = detector.compare(candidate_text, reference_text)
```

The path passed to `model_path` must name one ONNX model file. The
`tokenizer_path` directory must contain the matching tokenizer assets and
configuration. The backend loads tokenizers with `local_files_only=True`, so
missing files fail explicitly rather than causing a network download.

The backend accepts common ONNX outputs:
- A sentence-level embedding tensor shaped `[batch, hidden_size]`.
- Token-level hidden states shaped `[batch, sequence_length, hidden_size]`, which
  are mean-pooled using the attention mask so padding does not affect vectors.

The backend uses the model's available inputs and raises a descriptive error if
the tokenizer cannot supply one of them. Use a model exported for this interface;
exporting or quantizing a model is intentionally outside EvalGuard's runtime.

## Fallback chain

```python
from evalguard.contamination.semantic import (
    OnnxRuntimeBackend,
    SemanticDetector,
    SentenceTransformersBackend,
)

detector = SemanticDetector(
    backend=SentenceTransformersBackend(),
    fallback_backends=[
        OnnxRuntimeBackend(
            model_path="models/all-MiniLM-L6-v2/model_quantized.onnx",
            tokenizer_path="models/all-MiniLM-L6-v2",
        )
    ],
)
```

Configured backends are attempted in order. If all configured backends fail,
EvalGuard logs the failure and uses its zero-extra-dependency TF-IDF fallback.
This keeps semantic checks available, but TF-IDF similarity is lexical rather
than a substitute for transformer embeddings; deployments should inspect their
logs and configure the backend that matches their accuracy and resource needs.
