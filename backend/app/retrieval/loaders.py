import os
import pickle
import logging
from typing import Any, Optional, List, Dict
from dataclasses import dataclass

logger = logging.getLogger("agrigpt.retrieval.loaders")

@dataclass
class ParentChunk:
    id: str
    text: str
    heading: str
    page_start: int
    page_end: int
    source: str


@dataclass
class ChildChunk:
    id: str
    text: str
    parent_id: str
    page: int
    source: str
    heading: str
    embed_index: int = -1


@dataclass
class RetrievedChunk:
    child: ChildChunk
    parent: ParentChunk
    score: float
    retrieval_method: str
    reranker_score: float = 0.0
    hybrid_score: float = 0.0


class CustomUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if name == 'ChildChunk':
            return ChildChunk
        if name == 'ParentChunk':
            return ParentChunk
        if name == 'RetrievedChunk':
            return RetrievedChunk
        return super().find_class(module, name)


class ArtifactLoader:
    """
    Handles loading persisted FAISS, BM25, and hierarchical document mapping artifacts.
    Uses a CustomUnpickler to resolve notebook-scoped classes during deserialization.
    """
    def __init__(self, artifacts_dir: str):
        self.artifacts_dir = artifacts_dir

    def load_faiss_index(self) -> Optional[Any]:
        """
        Reads and loads the binary FAISS index from disk.
        """
        path = os.path.join(self.artifacts_dir, "faiss.index")
        if not os.path.exists(path):
            logger.warning(f"FAISS index file not found at: {path}. Dense retrieval will be disabled.")
            return None
        try:
            import faiss
            index = faiss.read_index(path)
            logger.info(f"FAISS vector index loaded successfully from {path}")
            return index
        except Exception as e:
            logger.error(f"Error loading FAISS index from {path}: {str(e)}")
            return None

    def load_pickle(self, filename: str) -> Optional[Any]:
        """
        Loads standard serialization pickle documents (e.g. child/parent maps)
        using CustomUnpickler.
        """
        path = os.path.join(self.artifacts_dir, filename)
        if not os.path.exists(path):
            logger.warning(f"Serialized pickle artifact '{filename}' not found at: {path}.")
            return None
        try:
            with open(path, "rb") as f:
                data = CustomUnpickler(f).load()
            logger.info(f"Loaded pickle file successfully from {path}")
            return data
        except Exception as e:
            logger.error(f"Error deserializing pickle file {path}: {str(e)}")
            return None
