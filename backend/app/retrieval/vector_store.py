import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger("agrigpt.retrieval.vector_store")

class VectorStoreRetriever:
    """
    Handles dense semantic retrieval by embedding incoming queries and searching a FAISS vector index.
    """
    def __init__(
        self,
        index: Any,
        child_docs: List[Dict[str, Any]],
        model_name: str = "all-MiniLM-L6-v2",
        top_k: int = 5
    ):
        self.index = index
        self.child_docs = child_docs
        self.model_name = model_name
        self.top_k = top_k
        self._model = None

    @property
    def model(self):
        """Lazy loader for SentenceTransformer model to optimize cold start times."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except Exception as e:
                logger.error(f"Failed to initialize SentenceTransformer model '{self.model_name}': {str(e)}")
                raise e
        return self._model

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Embeds the query and queries the FAISS index to find semantic matches.
        """
        if self.index is None or not self.child_docs:
            logger.warning("FAISS index or children documentation mappings are uninitialized. Returning empty results.")
            return []

        k = top_k or self.top_k
        try:
            # Generate query embedding
            query_embedding = self.model.encode([query], convert_to_numpy=True).astype("float32")
            
            # Query the FAISS index
            distances, indices = self.index.search(query_embedding, k)
            
            results = []
            for dist, idx in zip(distances[0], indices[0]):
                # FAISS returns -1 if there are insufficient elements in index
                if idx == -1 or idx >= len(self.child_docs):
                    continue
                
                doc = self.child_docs[idx]
                doc_copy = doc.copy()
                doc_copy["score"] = float(dist)  # FAISS L2 distance
                doc_copy["retrieval_type"] = "dense"
                results.append(doc_copy)
                
            return results
        except Exception as e:
            logger.error(f"Failed dense semantic retrieval operation: {str(e)}")
            return []
