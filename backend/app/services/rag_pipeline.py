import os
import re
import logging
from typing import Dict, Any, List, Tuple

# Suppress HuggingFace and Transformers Warnings
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_EXPERIMENTAL_WARNING"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import numpy as np
import tiktoken

from app.core.config import settings
from app.retrieval import (
    ArtifactLoader,
    ChildChunk,
    ParentChunk,
    RetrievedChunk
)

logger = logging.getLogger("agrigpt.services.rag_pipeline")

class RAGPipeline:
    def __init__(self):
        self.children = []
        self.parents = {}
        self.bm25_data = None
        self.faiss_index = None
        self.bm25 = None
        self.bm25_children = []
        self._embed_model_instance = None
        self._reranker_model_instance = None

    def initialize(self):
        """Eagerly load FAISS index, BM25 index, embedding model, and reranker model."""
        logger.info("Starting RAG Pipeline eager initialization...")
        
        artifacts_dir = os.path.abspath(settings.RAG_ARTIFACTS_DIR)
        if not os.path.exists(artifacts_dir) or not os.path.exists(os.path.join(artifacts_dir, "children.pkl")):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            fallback_dir = os.path.join(base_dir, settings.RAG_ARTIFACTS_DIR)
            if os.path.exists(fallback_dir) and os.path.exists(os.path.join(fallback_dir, "children.pkl")):
                artifacts_dir = fallback_dir
        
        logger.info(f"Initializing RAG retrieval pipeline with assets from: {artifacts_dir}")
        loader = ArtifactLoader(artifacts_dir)
        
        self.faiss_index = loader.load_faiss_index()
        logger.info("[STARTUP] FAISS loaded")
        print("[STARTUP] FAISS loaded", flush=True)
        
        self.children = loader.load_pickle("children.pkl") or []
        self.parents = loader.load_pickle("parents.pkl") or {}
        self.bm25_data = loader.load_pickle("bm25.pkl")
        logger.info("[STARTUP] BM25 loaded")
        print("[STARTUP] BM25 loaded", flush=True)
        
        if isinstance(self.bm25_data, dict):
            self.bm25 = self.bm25_data.get("bm25")
            self.bm25_children = self.bm25_data.get("children", self.children)
        else:
            self.bm25 = self.bm25_data
            self.bm25_children = self.children

        if isinstance(self.parents, list):
            self.parents = {p.id: p for p in self.parents}

        _ = self.embed_model
        logger.info("[STARTUP] Embedding model loaded")
        print("[STARTUP] Embedding model loaded", flush=True)

        _ = self.reranker_model
        logger.info("[STARTUP] Reranker loaded")
        print("[STARTUP] Reranker loaded", flush=True)

    @property
    def embed_model(self):
        if not hasattr(self, "_embed_model_instance") or self._embed_model_instance is None:
            import transformers
            transformers.logging.set_verbosity_error()
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {settings.EMBED_MODEL}")
            self._embed_model_instance = SentenceTransformer(settings.EMBED_MODEL, device="cpu")
        return self._embed_model_instance

    @property
    def reranker_model(self):
        if not hasattr(self, "_reranker_model_instance") or self._reranker_model_instance is None:
            import transformers
            transformers.logging.set_verbosity_error()
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading reranker model: {settings.RERANKER_MODEL}")
            self._reranker_model_instance = CrossEncoder(settings.RERANKER_MODEL, device="cpu")
        return self._reranker_model_instance

    def _tokenise(self, text: str) -> List[str]:
        return re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()

    def _normalise_scores(self, results: List[Tuple[Any, float]]) -> List[Tuple[Any, float]]:
        if not results:
            return []
        scores = [s for _, s in results]
        mn, mx = min(scores), max(scores)
        if mx == mn:
            return [(item, 1.0) for item, _ in results]
        return [(item, (s - mn) / (mx - mn)) for item, s in results]

    def _embed_query(self, query: str) -> np.ndarray:
        prefix = "Represent this sentence for searching relevant passages: "
        return self.embed_model.encode(
            [prefix + query],
            normalize_embeddings=True
        ).astype("float32")

    def _dense_search(self, query: str, top_k: int = 10) -> List[Tuple[ChildChunk, float]]:
        if self.faiss_index is None or not self.children:
            return []
        q_emb = self._embed_query(query)
        scores, indices = self.faiss_index.search(q_emb, top_k)
        results = [
            (self.children[idx], float(s))
            for s, idx in zip(scores[0], indices[0])
            if idx != -1 and idx < len(self.children)
        ]
        return sorted(results, key=lambda x: x[1], reverse=True)

    def _sparse_search(self, query: str, top_k: int = 10) -> List[Tuple[ChildChunk, float]]:
        if self.bm25 is None or not self.bm25_children:
            return []
        tokens = self._tokenise(query)
        scores = self.bm25.get_scores(tokens)
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [(self.bm25_children[i], float(scores[i])) for i in top_idx if scores[i] > 0]

    def _hybrid_search(
        self,
        query: str,
        faiss_top_k: int = 10,
        bm25_top_k: int = 10,
        alpha: float = 0.5
    ) -> List[Tuple[ChildChunk, float, str]]:
        dense_raw = self._dense_search(query, faiss_top_k)
        sparse_raw = self._sparse_search(query, bm25_top_k)
        dense_norm = self._normalise_scores(dense_raw)
        sparse_norm = self._normalise_scores(sparse_raw)
        
        merged: Dict[str, Tuple[ChildChunk, float, str]] = {}
        for chunk, score in dense_norm:
            merged[chunk.id] = (chunk, alpha * score, "faiss")
        for chunk, score in sparse_norm:
            if chunk.id in merged:
                prev_chunk, prev_score, _ = merged[chunk.id]
                merged[chunk.id] = (prev_chunk, prev_score + (1 - alpha) * score, "hybrid")
            else:
                merged[chunk.id] = (chunk, (1 - alpha) * score, "bm25")
        return sorted(merged.values(), key=lambda x: x[1], reverse=True)

    def _rerank_results(
        self,
        query: str,
        candidates: List[Tuple[ChildChunk, float, str]],
        pool_size: int = 20,
        top_n: int = 5
    ) -> List[RetrievedChunk]:
        pool = candidates[:pool_size]
        if not pool:
            return []
        pairs = [(query, chunk.text) for chunk, _, _ in pool]
        scores = self.reranker_model.predict(pairs).tolist()
        ranked = sorted(zip(pool, scores), key=lambda x: x[1], reverse=True)[:top_n]
        
        results = []
        for (chunk, hybrid_score, method), rr_score in ranked:
            parent = self.parents.get(chunk.parent_id)
            if parent is None:
                continue
            results.append(RetrievedChunk(
                child=chunk, parent=parent,
                score=float(rr_score),
                retrieval_method=method,
                reranker_score=float(rr_score),
                hybrid_score=float(hybrid_score),
            ))
        return results

    def _deduplicate_results(self, results: List[RetrievedChunk], sim_threshold: float = 0.88) -> List[RetrievedChunk]:
        if len(results) <= 1:
            return results
        texts = [rc.child.text for rc in results]
        embs = self.embed_model.encode(texts, normalize_embeddings=True).astype("float32")
        sim_matrix = embs @ embs.T
        kept, kept_indices = [], []
        for i, rc in enumerate(results):
            if not kept_indices:
                kept.append(rc)
                kept_indices.append(i)
                continue
            max_sim = max(float(sim_matrix[i, j]) for j in kept_indices)
            if max_sim < sim_threshold:
                kept.append(rc)
                kept_indices.append(i)
        return kept

    def _build_context(self, results: List[RetrievedChunk], token_budget: int = 2500, use_parent_text: bool = True) -> str:
        if not results:
            return "No relevant context found."
            
        encoder = tiktoken.get_encoding("cl100k_base")
        parts, used_tokens, seen_parent_ids = [], 0, set()
        
        for i, rc in enumerate(results, 1):
            content_text = rc.parent.text if use_parent_text else rc.child.text
            parent_id = rc.parent.id
            if parent_id in seen_parent_ids:
                content_text = rc.child.text
            seen_parent_ids.add(parent_id)
            
            header = (
                f"SOURCE {i}:\n"
                f"Document : {rc.parent.source}\n"
                f"Section  : {rc.parent.heading}\n"
                f"Pages    : {rc.parent.page_start}–{rc.parent.page_end}\n"
                f"Method   : {rc.retrieval_method}  "
                f"(reranker={rc.reranker_score:.4f}, hybrid={rc.hybrid_score:.4f})\n"
                f"{'-' * 60}\n"
            )
            
            block = header + content_text
            block_tokens = encoder.encode(block)
            
            if used_tokens + len(block_tokens) > token_budget:
                remaining = token_budget - used_tokens
                header_tokens = encoder.encode(header)
                if remaining > len(header_tokens) + 20:
                    allowed_content_tokens = remaining - len(header_tokens) - 5
                    truncated_content_tokens = encoder.encode(content_text)[:allowed_content_tokens]
                    truncated_content = encoder.decode(truncated_content_tokens)
                    parts.append(header + truncated_content + " [truncated]")
                break
                
            parts.append(block)
            used_tokens += len(block_tokens)
            
        return "\n\n".join(parts)

    def query(self, question: str) -> Dict[str, Any]:
        """Runs the complete RAG query pipeline synchronously (FAISS -> BM25 -> Rerank -> Dedup)."""
        hybrid_candidates = self._hybrid_search(
            question,
            faiss_top_k=settings.RETRIEVAL_TOP_K,
            bm25_top_k=settings.RETRIEVAL_TOP_K
        )
        
        # Logging details for BUG 4 verification:
        logger.info(f"=== RAG RETRIEVAL LOGS FOR QUERY: '{question}' ===")
        print(f"\n=== RAG RETRIEVAL LOGS FOR QUERY: '{question}' ===")
        logger.info(f"Top {len(hybrid_candidates)} retrieved hybrid candidates before reranking:")
        print(f"Top {len(hybrid_candidates)} retrieved hybrid candidates before reranking:")
        for idx, (chunk, score, method) in enumerate(hybrid_candidates[:settings.RETRIEVAL_TOP_K * 2]):
            logger.info(f"  Candidate {idx + 1}: ID={chunk.id} | Score={score:.4f} | Method={method} | Snippet='{chunk.text[:60].strip()}...'")
            print(f"  Candidate {idx + 1}: ID={chunk.id} | Score={score:.4f} | Method={method} | Snippet='{chunk.text[:60].strip()}...'")

        reranked = self._rerank_results(
            question,
            hybrid_candidates,
            pool_size=settings.RETRIEVAL_TOP_K * 2,
            top_n=settings.RERANK_TOP_K
        )
        
        # Log reranked order and similarity scores
        logger.info(f"Reranked order (Similarity scores after cross-encoder):")
        print(f"Reranked order (Similarity scores after cross-encoder):")
        for idx, rc in enumerate(reranked):
            logger.info(f"  Reranked {idx + 1}: Doc='{rc.parent.source}' | Section='{rc.parent.heading}' | Reranker Score={rc.reranker_score:.4f} | Hybrid Score={rc.hybrid_score:.4f} | Method={rc.retrieval_method}")
            print(f"  Reranked {idx + 1}: Doc='{rc.parent.source}' | Section='{rc.parent.heading}' | Reranker Score={rc.reranker_score:.4f} | Hybrid Score={rc.hybrid_score:.4f} | Method={rc.retrieval_method}")

        deduped = self._deduplicate_results(reranked, sim_threshold=0.88)
        
        logger.info(f"Deduplicated to {len(deduped)} documents:")
        print(f"Deduplicated to {len(deduped)} documents:")
        for idx, rc in enumerate(deduped):
            logger.info(f"  Kept {idx + 1}: Doc='{rc.parent.source}' | Section='{rc.parent.heading}' | Reranker Score={rc.reranker_score:.4f}")
            print(f"  Kept {idx + 1}: Doc='{rc.parent.source}' | Section='{rc.parent.heading}' | Reranker Score={rc.reranker_score:.4f}")

        context = self._build_context(deduped, token_budget=2500)
        
        # Log final context token length
        encoder = tiktoken.get_encoding("cl100k_base")
        context_token_len = len(encoder.encode(context))
        logger.info(f"Final prompt context length: {context_token_len} tokens")
        print(f"Final prompt context length: {context_token_len} tokens")
        logger.info("====================================================")
        print("====================================================\n")

        sources = [
            {
                "document": rc.parent.source,
                "section": rc.parent.heading,
                "pages": f"{rc.parent.page_start}–{rc.parent.page_end}",
                "method": rc.retrieval_method,
                "reranker_score": round(rc.reranker_score, 4),
                "hybrid_score": round(rc.hybrid_score, 4)
            }
            for rc in deduped
        ]
        return {
            "query": question,
            "context": context,
            "sources": sources,
            "n_final": len(deduped)
        }
