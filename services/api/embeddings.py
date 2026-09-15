"""Kiddo Assist — shared embedding / rerank backends (Iteration 3, RAG).

Guide §4 spec: BAAI/bge-m3 (dense 1024-d) + BAAI/bge-reranker-base via
`FlagEmbedding`. Some transformers releases (>= ~4.51) reject FlagEmbedding's
`dtype` kwarg on XLMRobertaModel (TypeError: unexpected keyword argument
'dtype'). The real path here therefore tries, in order:

  1. FlagEmbedding (BGEM3FlagModel / FlagReranker) — the documented stack, used
     on environments where it loads cleanly.
  2. A direct transformers load of the same weights — CLS pooling +
     L2-normalize for bge-m3, sequence-classification head + sigmoid for the
     reranker. Produces the same 1024-d dense vectors from the same weights.

The deterministic sim backend (KIDDO_SEED_BACKEND=sim / KIDDO_RAG_BACKEND=sim)
is used by the offline test suite — no downloads, stable ordering.

Consistency note: stored vectors and query vectors must share a backend. The
backend is read from the environment once per process, so a seed + retrieve in
the same run agree automatically; because `seed.py` is destructive-idempotent,
re-running it after any backend change keeps `data/` consistent.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re

logger = logging.getLogger("kiddo.embeddings")


def sim_mode() -> bool:
    """True when a deterministic backend is requested (tests / no-model env)."""
    for env in ("KIDDO_RAG_BACKEND", "KIDDO_SEED_BACKEND"):
        if os.getenv(env, "").lower() == "sim":
            return True
    return False


def _l2_normalize(rows) -> list[list[float]]:
    import numpy as np

    arr = np.asarray(rows, dtype="float32")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (arr / norms).tolist()


# ---------------------------------------------------------------------------
# Embedders
# ---------------------------------------------------------------------------


class SimEmbedder:
    """Deterministic hash-BoW embedder (offline tests only).

    Each word maps to ±1 on a hashed dimension; vectors are L2-normalized so
    cosine similarity is meaningful (texts sharing words rank higher).
    """

    DIM = 1024

    def encode_many(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.DIM
            for token in re.findall(r"[a-z']+", text.lower()):
                h = hashlib.sha256(token.encode("utf-8")).digest()
                idx = int.from_bytes(h[:4], "big") % self.DIM
                sign = 1.0 if h[4] % 2 == 0 else -1.0
                vec[idx] += sign
            norm = sum(v * v for v in vec) ** 0.5 or 1.0
            out.append([v / norm for v in vec])
        return out


class BgeM3Embedder:
    """Real bge-m3 dense embeddings (FlagEmbedding → direct transformers)."""

    _state: tuple | None = None  # ("flag", model) | ("tf", model, tokenizer)

    def _ensure(self):
        if self._state is not None:
            return self._state
        kind = None
        try:
            from FlagEmbedding import BGEM3FlagModel

            kind = ("flag", BGEM3FlagModel("BAAI/bge-m3", use_fp16=False, devices="cpu"))
        except Exception as exc:
            logger.warning(
                f"FlagEmbedding bge-m3 unavailable ({exc}); using direct transformers load."
            )
        if kind is None:
            from transformers import AutoModel, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-m3")
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token
            model = AutoModel.from_pretrained("BAAI/bge-m3")
            model.eval()
            kind = ("tf", model, tokenizer)
        self._state = kind
        return self._state

    def encode_many(self, texts: list[str]) -> list[list[float]]:
        kind = self._ensure()
        if kind[0] == "flag":
            dense = kind[1].encode(texts, return_dense=True, batch_size=8)["dense_vecs"]
            return _l2_normalize(dense)
        import torch

        with torch.no_grad():
            enc = kind[2](texts, padding=True, truncation=True, max_length=512, return_tensors="pt")
            out = kind[1](**enc)
        cls_vecs = out.last_hidden_state[:, 0]  # CLS pooling
        return _l2_normalize(cls_vecs.numpy())


def make_embedder():
    """Pick the embedder for the current environment."""
    return SimEmbedder() if sim_mode() else BgeM3Embedder()


# ---------------------------------------------------------------------------
# Reranker (bge-reranker-base)
# ---------------------------------------------------------------------------


class BgeReranker:
    """Cross-encoder reranker (FlagEmbedding → direct transformers)."""

    _state: tuple | None = None  # ("flag", model) | ("tf", model, tokenizer)

    def _ensure(self):
        if self._state is not None:
            return self._state
        kind = None
        try:
            from FlagEmbedding import FlagReranker

            kind = ("flag", FlagReranker("BAAI/bge-reranker-base", use_fp16=False))
        except Exception as exc:
            logger.warning(
                f"FlagEmbedding reranker unavailable ({exc}); using direct transformers load."
            )
        if kind is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-reranker-base")
            model = AutoModelForSequenceClassification.from_pretrained("BAAI/bge-reranker-base")
            model.eval()
            kind = ("tf", model, tokenizer)
        self._state = kind
        return self._state

    def rerank(self, query: str, chunks: list[dict]) -> list[float]:
        pairs = [[query.strip(), c.get("text_chunk") or c.get("content_item_id", "")] for c in chunks]
        kind = self._ensure()
        if kind[0] == "flag":
            scores = kind[1].compute_score(pairs)
            if isinstance(scores, float):
                scores = [scores]
            return [float(s) for s in scores]
        import torch

        with torch.no_grad():
            enc = kind[2](pairs, padding=True, truncation=True, return_tensors="pt")
            logits = kind[1](**enc).logits
        # Cross-encoder logit → probability; ordering is preserved either way.
        probs = torch.sigmoid(logits.squeeze(-1))
        return [float(p) for p in probs]


def make_reranker():
    """Pick the reranker for the current environment (sim is a no-op rescore)."""
    if sim_mode():
        # Sim retrieval already orders by cosine; rerank passes scores through.
        class _SimReranker:
            def rerank(self, query: str, chunks: list[dict]) -> list[float]:
                return [float(c.get("score", 0.0)) for c in chunks]

        return _SimReranker()
    return BgeReranker()