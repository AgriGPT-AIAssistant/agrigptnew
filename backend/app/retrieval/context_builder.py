import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger("agrigpt.retrieval.context_builder")


@dataclass
class ContextConfig:
    max_tokens: int = 3000          # Approximate character budget (~4 chars/token)
    separator: str = "\n\n---\n\n"  # Section divider between chunks
    include_sources: bool = True     # Append source metadata footer


@dataclass
class RetrievalContext:
    context_text: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    token_estimate: int = 0
    chunk_count: int = 0


class ContextBuilder:
    """
    Assembles a ranked list of retrieved document chunks into a clean, ordered
    context string suitable for LLM prompt injection.

    Responsibilities:
    - Expand child chunks to parent documents where available
    - Enforce approximate token budget
    - Preserve source metadata for attribution
    - Maintain chunk ordering for coherent context flow
    """

    def __init__(
        self,
        parent_docs: Optional[Dict[str, Any]] = None,
        config: Optional[ContextConfig] = None,
    ):
        # parent_docs: maps child chunk id → parent document dict
        self.parent_docs = parent_docs or {}
        self.config = config or ContextConfig()

    def _extract_text(self, doc: Dict[str, Any]) -> str:
        return (
            doc.get("text")
            or doc.get("content")
            or doc.get("page_content")
            or ""
        ).strip()

    def _extract_source(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": doc.get("id") or doc.get("chunk_id", "unknown"),
            "source": doc.get("source") or doc.get("metadata", {}).get("source", "unknown"),
            "page": doc.get("page") or doc.get("metadata", {}).get("page"),
            "rerank_score": doc.get("rerank_score"),
        }

    def _resolve_text(self, doc: Dict[str, Any]) -> str:
        """
        Attempts to expand a child chunk to its parent document for richer context.
        Falls back to the child chunk text if no parent mapping exists.
        """
        doc_id = doc.get("id") or doc.get("chunk_id")
        if doc_id and doc_id in self.parent_docs:
            parent = self.parent_docs[doc_id]
            parent_text = self._extract_text(parent)
            if parent_text:
                return parent_text
        return self._extract_text(doc)

    def build(self, ranked_docs: List[Dict[str, Any]]) -> RetrievalContext:
        """
        Assembles ranked docs into a prompt-ready context string.
        Respects approximate character budget and preserves source attribution.
        """
        if not ranked_docs:
            logger.warning("ContextBuilder received empty doc list — returning empty context.")
            return RetrievalContext(context_text="", sources=[], token_estimate=0, chunk_count=0)

        char_budget = self.config.max_tokens * 4  # ~4 chars per token
        sections: List[str] = []
        sources: List[Dict[str, Any]] = []
        total_chars = 0
        seen_ids: set = set()

        for doc in ranked_docs:
            doc_id = doc.get("id") or doc.get("chunk_id") or id(doc)

            # Skip exact duplicates that survived deduplication
            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)

            text = self._resolve_text(doc)
            if not text:
                continue

            chunk_chars = len(text) + len(self.config.separator)
            if total_chars + chunk_chars > char_budget:
                logger.info(
                    f"Token budget reached at chunk {len(sections) + 1}. "
                    f"Remaining {len(ranked_docs) - len(sections)} chunks truncated."
                )
                break

            sections.append(text)
            sources.append(self._extract_source(doc))
            total_chars += chunk_chars

        context_text = self.config.separator.join(sections)

        # Append source attribution block if enabled
        if self.config.include_sources and sources:
            attribution_lines = ["**Sources:**"]
            for i, src in enumerate(sources, 1):
                page_info = f", p.{src['page']}" if src.get("page") else ""
                attribution_lines.append(f"  [{i}] {src['source']}{page_info}")
            context_text += "\n\n" + "\n".join(attribution_lines)

        token_estimate = total_chars // 4

        logger.info(
            f"ContextBuilder assembled {len(sections)} chunks, "
            f"~{token_estimate} tokens from {len(ranked_docs)} candidates."
        )

        return RetrievalContext(
            context_text=context_text,
            sources=sources,
            token_estimate=token_estimate,
            chunk_count=len(sections),
        )
