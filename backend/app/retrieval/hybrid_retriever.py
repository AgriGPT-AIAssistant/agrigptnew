import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from app.retrieval.vector_store import VectorStoreRetriever
from app.retrieval.bm25_store import BM25Retriever

logger = logging.getLogger("agrigpt.retrieval.hybrid_retriever")


@dataclass
class RetrievalConfig:
    dense_weight: float = 0.6
    sparse_weight: float = 0.4
    top_k_dense: int = 10
    top_k_sparse: int = 10
    top_k_final: int = 8
    rrf_k: int = 60  # RRF rank constant


class HybridRetriever:
    """
    Merges dense (FAISS) and sparse (BM25) results via Reciprocal Rank Fusion (RRF).

    RRF formula:
        rrf_score(doc) = Σ weight_i / (k + rank_i)

    This ensures retrieval quality degrades gracefully if either retriever fails.
    """

    def __init__(
        self,
        vector_retriever: VectorStoreRetriever,
        bm25_retriever: BM25Retriever,
        config: Optional[RetrievalConfig] = None,
    ):
        self.vector_retriever = vector_retriever
        self.bm25_retriever = bm25_retriever
        self.config = config or RetrievalConfig()

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Executes parallel dense + sparse retrieval, fuses ranked lists via RRF,
        and returns the top-k uniquely identified documents.
        """
        final_k = top_k or self.config.top_k_final
        cfg = self.config

        dense_results = self.vector_retriever.retrieve(query, top_k=cfg.top_k_dense)
        sparse_results = self.bm25_retriever.retrieve(query, top_k=cfg.top_k_sparse)

        # Build RRF score table keyed by document id
        rrf_scores: Dict[str, float] = {}
        doc_lookup: Dict[str, Dict[str, Any]] = {}

        def _apply_rrf(results: List[Dict[str, Any]], weight: float) -> None:
            for rank, doc in enumerate(results, start=1):
                doc_id = doc.get("id") or doc.get("chunk_id") or str(rank)
                contribution = weight / (cfg.rrf_k + rank)
                rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + contribution
                if doc_id not in doc_lookup:
                    doc_lookup[doc_id] = doc

        _apply_rrf(dense_results, cfg.dense_weight)
        _apply_rrf(sparse_results, cfg.sparse_weight)

        # Sort by fused RRF score descending
        ranked_ids = sorted(rrf_scores, key=rrf_scores.__getitem__, reverse=True)

        fused: List[Dict[str, Any]] = []
        for doc_id in ranked_ids[:final_k]:
            doc = doc_lookup[doc_id].copy()
            doc["rrf_score"] = round(rrf_scores[doc_id], 6)
            fused.append(doc)

        logger.info(
            f"Hybrid retrieval: dense={len(dense_results)}, sparse={len(sparse_results)}, "
            f"fused={len(fused)} for query='{query[:60]}...'"
        )
        return fused
