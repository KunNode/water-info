"""Knowledge base orchestration service."""

from __future__ import annotations

import hashlib
import logging
from dataclasses import asdict

from app.config import get_settings
from app.database import get_db_service
from app.rag.embedder import get_embedding_client
from app.rag.loader import detect_mime, load_plain_document, load_uploaded_document
from app.rag.models import SearchResult
from app.rag.retriever import hybrid_search
from app.rag.splitter import split_loaded_document
from app.state import Evidence

logger = logging.getLogger(__name__)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def build_evidence(results: list[SearchResult | dict]) -> list[Evidence]:
    evidence: list[Evidence] = []
    for index, result in enumerate(results, start=1):
        if isinstance(result, dict):
            content = str(result.get("content") or "")
            document_title = str(result.get("document_title") or "")
            source_uri = str(result.get("source_uri") or "")
            heading_path = list(result.get("heading_path") or [])
            score = float(result.get("score") or 0.0)
        else:
            content = result.content
            document_title = result.document_title
            source_uri = result.source_uri
            heading_path = list(result.heading_path)
            score = float(result.score)
        evidence.append(
            Evidence(
                citation_id=f"[{index}]",
                content=content,
                document_title=document_title,
                source_uri=source_uri,
                heading_path=heading_path,
                score=score,
            )
        )
    return evidence


def format_evidence_markdown(evidence: list[Evidence]) -> str:
    if not evidence:
        return "未命中知识库。"
    lines = ["## 证据片段"]
    for item in evidence:
        heading = " / ".join(item.heading_path) if item.heading_path else "正文"
        source = f" - {item.source_uri}" if item.source_uri else ""
        lines.append(f"- {item.citation_id} **{item.document_title}** / {heading}{source}")
        lines.append(f"  {item.content[:220].strip()}")
    return "\n".join(lines)


class KnowledgeBaseService:
    async def create_upload_job(
        self,
        *,
        filename: str,
        content: bytes,
        title: str | None,
        source_uri: str,
        mime: str | None,
        created_by: str,
    ) -> tuple[str, str]:
        db = get_db_service()
        document = await db.upsert_kb_document_shell(
            title=title or filename,
            source_type="upload",
            source_uri=source_uri or filename,
            mime=detect_mime(filename, mime),
            content_hash=_sha256_bytes(content),
            file_size=len(content),
            created_by=created_by,
        )
        job_id = await db.create_kb_ingest_job(document["id"])
        return str(document["id"]), str(job_id)

    async def ingest_document_bytes(
        self,
        *,
        document_id: str,
        job_id: str,
        filename: str,
        content: bytes,
        title: str | None = None,
        source_uri: str = "",
        mime: str | None = None,
        created_by: str = "",
    ) -> None:
        db = get_db_service()
        settings = get_settings()
        await db.update_kb_document_status(document_id, "processing")

        try:
            loaded = load_uploaded_document(filename, content, title=title, mime=mime)
            chunks = split_loaded_document(
                loaded,
                target_tokens=settings.rag_chunk_size,
                overlap_tokens=settings.rag_chunk_overlap,
            )
            if not chunks:
                raise RuntimeError("文档解析后没有可索引文本")

            embed_client = get_embedding_client()
            embeddings: list[list[float]] | None = None
            embedding_model = ""
            if embed_client.is_enabled:
                try:
                    embeddings = await embed_client.embed_texts([chunk.content for chunk in chunks])
                    embedding_model = settings.embedding_model
                except Exception as exc:
                    logger.warning("document %s embedding failed, fallback to keyword only: %s", document_id, exc)

            await db.replace_kb_document_chunks(
                document_id=document_id,
                title=loaded.title,
                source_uri=source_uri or filename,
                mime=loaded.mime,
                raw_text=loaded.raw_text,
                metadata=loaded.metadata,
                chunk_candidates=chunks,
                embedding_model=embedding_model,
                embeddings=embeddings,
            )
            await db.finish_kb_ingest_job(job_id, "completed")
        except Exception as exc:
            await db.update_kb_document_status(document_id, "failed")
            await db.finish_kb_ingest_job(job_id, "failed", error=str(exc))
            raise

    async def reindex_document(self, document_id: str, *, job_id: str) -> None:
        db = get_db_service()
        settings = get_settings()
        row = await db.get_kb_document(document_id)
        if not row:
            raise RuntimeError("文档不存在")

        raw_text = str(row.get("raw_text") or "").strip()
        if not raw_text:
            raise RuntimeError("文档缺少可重建文本")

        await db.update_kb_document_status(document_id, "processing")
        try:
            loaded = load_plain_document(str(row["title"]), raw_text, str(row["mime"]))
            chunks = split_loaded_document(
                loaded,
                target_tokens=settings.rag_chunk_size,
                overlap_tokens=settings.rag_chunk_overlap,
            )
            embed_client = get_embedding_client()
            embeddings: list[list[float]] | None = None
            embedding_model = ""
            if embed_client.is_enabled:
                try:
                    embeddings = await embed_client.embed_texts([chunk.content for chunk in chunks])
                    embedding_model = settings.embedding_model
                except Exception as exc:
                    logger.warning("document %s reindex embedding failed: %s", document_id, exc)

            await db.replace_kb_document_chunks(
                document_id=document_id,
                title=str(row["title"]),
                source_uri=str(row.get("source_uri") or ""),
                mime=str(row["mime"]),
                raw_text=loaded.raw_text,
                metadata=dict(row.get("metadata") or {}),
                chunk_candidates=chunks,
                embedding_model=embedding_model,
                embeddings=embeddings,
            )
            await db.finish_kb_ingest_job(job_id, "completed")
        except Exception as exc:
            await db.update_kb_document_status(document_id, "failed")
            await db.finish_kb_ingest_job(job_id, "failed", error=str(exc))
            raise

    async def search(self, query: str, *, top_k: int = 5, source_types: list[str] | None = None) -> list[SearchResult]:
        try:
            return await hybrid_search(query, top_k=top_k, source_types=source_types)
        except Exception as exc:
            logger.warning("knowledge search fallback to empty result: %s", exc)
            return []


async def search_knowledge_base(
    query: str,
    *,
    top_k: int | None = None,
    source_types: list[str] | None = None,
) -> list[dict]:
    settings = get_settings()
    results = await get_knowledge_base_service().search(
        query,
        top_k=top_k or settings.rag_top_k,
        source_types=source_types,
    )
    return [asdict(result) for result in results]


_knowledge_base_service: KnowledgeBaseService | None = None


def get_knowledge_base_service() -> KnowledgeBaseService:
    global _knowledge_base_service
    if _knowledge_base_service is None:
        _knowledge_base_service = KnowledgeBaseService()
    return _knowledge_base_service
