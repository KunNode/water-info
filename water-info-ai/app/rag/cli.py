"""CLI helpers for knowledge base ingestion."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.rag.service import get_knowledge_base_service


async def _ingest(path: Path, title: str | None = None) -> None:
    content = path.read_bytes()
    service = get_knowledge_base_service()
    document_id, job_id = await service.create_upload_job(
        filename=path.name,
        content=content,
        title=title,
        source_uri=str(path),
        mime=None,
        created_by="cli",
    )
    await service.ingest_document_bytes(
        document_id=document_id,
        job_id=job_id,
        filename=path.name,
        content=content,
        title=title,
        source_uri=str(path),
        created_by="cli",
    )
    print(document_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Knowledge base CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="ingest a single document")
    ingest_parser.add_argument("path", type=Path)
    ingest_parser.add_argument("--title")

    args = parser.parse_args()
    if args.command == "ingest":
        asyncio.run(_ingest(args.path, title=args.title))


if __name__ == "__main__":
    main()
