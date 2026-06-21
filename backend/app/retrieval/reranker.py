import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

logger = logging.getLogger("agrigpt.retrieval.reranker")


@dataclass
class RerankerConfig:
    model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    top_k: int = 5
    dedup_threshold: float = 0.92  # Cosine similarity above which chunks are considered duplicates


class CrossEncoderReranker:
    """
    Reranks a candidate list of retrieved documents with a CrossEncoder model for
    improved relevance precision. Includes semantic deduplication prior to reranking.
    """

    def __init__(self, config: Optional[RerankerConfig] = None):
        self.config = config or RerankerConfig()
        self._model = None

    @property
    def model(self):
        """Lazy-loads the CrossEncoder model to avoid cold-start overhead on import."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.config.model_name)
                logger.info(f"CrossEncoder reranker model loaded: {self.config.model_name}")
            except Exception as e:
                logger.error(f"Failed to load CrossEncoder model: {str(e)}")
                raise
        return self._model

    def _extract_text(self, doc: Dict[str, Any]) -> str:
        """Extracts a representative text field from the document dict."""
        return (
            doc.get("text")
            or doc.get("content")
            or doc.get("page_content")
            or ""
        )

    def deduplicate(self, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Removes semantically redundant chunks using cosine similarity of text hashes.
        Uses a lightweight fingerprint approach to avoid loading an additional encoder.
        """
        seen_fingerprints: List[str] = []
        unique_docs: List[Dict[str, Any]] = []

        for doc in docs:
            text = self._extract_text(doc).strip().lower()
            # Build a lightweight n-gram fingerprint from first 200 chars
            fingerprint = text[:200]
            is_duplicate = any(
                _jaccard_similarity(fingerprint, seen) >= self.config.dedup_threshold
                for seen in seen_fingerprints
            )
            if not is_duplicate:
                seen_fingerprints.append(fingerprint)
                unique_docs.append(doc)

        removed = len(docs) - len(unique_docs)
        if removed:
            logger.info(f"Deduplication removed {removed} redundant chunk(s).")
        return unique_docs

    def rerank(self, query: str, docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicates candidates then reranks them with a CrossEncoder score.
        Returns top_k documents sorted by descending relevance score.
        """
        if not docs:
            return []

        unique_docs = self.deduplicate(docs)

        pairs = [(query, self._extract_text(doc)) for doc in unique_docs]

        try:
            scores = self.model.predict(pairs)
        except Exception as e:
            logger.error(f"CrossEncoder prediction failed: {str(e)}. Returning deduplicated list unranked.")
            return unique_docs[: self.config.top_k]

        scored = sorted(
            zip(scores, unique_docs),
            key=lambda x: x[0],
            reverse=True,
        )

        results = []
        for score, doc in scored[: self.config.top_k]:
            doc_copy = doc.copy()
            doc_copy["rerank_score"] = round(float(score), 6)
            results.append(doc_copy)

        logger.info(f"Reranker selected top {len(results)} docs from {len(unique_docs)} candidates.")
        return results


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _jaccard_similarity(a: str, b: str) -> float:
    """Lightweight Jaccard similarity over character trigrams for dedup fingerprinting."""
    def trigrams(s: str):
        return set(s[i : i + 3] for i in range(len(s) - 2))

    set_a, set_b = trigrams(a), trigrams(b)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)
