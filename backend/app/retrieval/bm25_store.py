import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger("agrigpt.retrieval.bm25_store")

class BM25Retriever:
    """
    Handles sparse keyword-based retrieval using tokenized documents indexed with BM25.
    Optimizes finding exact agricultural term matches (like specific crop names or chemicals).
    """
    def __init__(
        self,
        bm25: Any,
        child_docs: List[Dict[str, Any]],
        top_k: int = 5
    ):
        self.bm25 = bm25
        self.child_docs = child_docs
        self.top_k = top_k

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Tokenizes the query and evaluates matches against pre-persisted BM25 corpus indexes.
        """
        if self.bm25 is None or not self.child_docs:
            logger.warning("BM25 model index or children documentation mappings are uninitialized. Returning empty results.")
            return []

        k = top_k or self.top_k
        try:
            # Basic lower-cased whitespace tokenizer matching precomputed index tokens
            query_tokens = [token.strip().lower() for token in query.split() if token.strip()]
            
            if not query_tokens:
                return []

            # Fetch score metrics for token lists
            scores = self.bm25.get_scores(query_tokens)
            
            # Retrieve top matching indices
            top_indices = np.argsort(scores)[::-1][:k]
            
            results = []
            for idx in top_indices:
                score = scores[idx]
                # Filter out documents with zero relevance matches
                if score <= 0:
                    continue
                
                doc = self.child_docs[idx]
                doc_copy = doc.copy()
                doc_copy["score"] = float(score)
                doc_copy["retrieval_type"] = "sparse"
                results.append(doc_copy)
                
            return results
        except Exception as e:
            logger.error(f"Failed sparse BM25 keyword retrieval operation: {str(e)}")
            return []
