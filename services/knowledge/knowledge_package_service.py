"""Knowledge Package Service (File Center).

A "package" is a named ``DocumentBatch`` scoped to one diagram. It groups the
sources (PDF, DOCX, pasted text, web snapshots) a user curates for a diagram,
and exposes the completed document IDs used to scope RAG retrieval.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.diagrams import Diagram
from models.domain.knowledge_space import DocumentBatch, KnowledgeDocument
from services.knowledge import package_wiki_store
from services.knowledge.knowledge_space_service import KnowledgeSpaceService
from services.knowledge.package_rag_scope import PackageRagScope, resolve_diagram_rag_scope
from services.utils.safe_upload import ensure_within_directory

logger = logging.getLogger(__name__)

# Recognised ingest sources for a package (UI badges, lifecycle).
PACKAGE_SOURCES = ("canvas", "knowledge_space", "chrome_extension", "doc_summary")

MAX_PACKAGES_PER_USER = 3

# Text-source MIME type stored on disk as markdown.
TEXT_SOURCE_FILE_TYPE = "text/markdown"


def _slugify_title(title: str, fallback: str) -> str:
    """Produce a filesystem-safe base name from a human title."""
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\- ]+", "", title or "").strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:80] or fallback


class KnowledgePackageService:
    """Manage File Center packages and their sources for a single user."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id
        self.ks = KnowledgeSpaceService(db, user_id)

    async def create_package(
        self,
        name: str,
        diagram_id: Optional[str] = None,
        source: str = "canvas",
    ) -> DocumentBatch:
        """Create a named package (DocumentBatch) for this user."""
        existing = await self.list_packages()
        non_summary = [pkg for pkg in existing if pkg.source != "doc_summary"]
        if len(non_summary) >= MAX_PACKAGES_PER_USER:
            raise ValueError(f"Maximum {MAX_PACKAGES_PER_USER} packages allowed per user")

        clean_name = (name or "").strip() or "Untitled package"
        package_source = source if source in PACKAGE_SOURCES else "canvas"

        package = DocumentBatch(
            user_id=self.user_id,
            name=clean_name[:200],
            diagram_id=diagram_id,
            source=package_source,
            status="pending",
            total_count=0,
            completed_count=0,
            failed_count=0,
        )
        self.db.add(package)
        await self.db.commit()
        await self.db.refresh(package)

        # Document Summary links via DocumentBatch.diagram_id only — never overwrite
        # diagrams.knowledge_package_id (that column is for Knowledge Space / File Center).
        if diagram_id and package_source != "doc_summary":
            await self._link_diagram_to_package(diagram_id, package.id)

        logger.info(
            "[FileCenter] Created package id=%s name='%s' diagram=%s source=%s user=%s",
            package.id,
            clean_name,
            diagram_id,
            package_source,
            self.user_id,
        )
        return package

    async def get_package(self, package_id: int) -> Optional[DocumentBatch]:
        """Fetch a package owned by this user (named packages only)."""
        result = await self.db.execute(
            select(DocumentBatch).where(
                and_(
                    DocumentBatch.id == package_id,
                    DocumentBatch.user_id == self.user_id,
                )
            )
        )
        return result.scalars().first()

    async def list_packages(self) -> List[DocumentBatch]:
        """List this user's named packages (newest first)."""
        result = await self.db.execute(
            select(DocumentBatch)
            .where(
                and_(
                    DocumentBatch.user_id == self.user_id,
                    DocumentBatch.name.isnot(None),
                )
            )
            .order_by(DocumentBatch.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_package_for_diagram(self, diagram_id: str) -> Optional[DocumentBatch]:
        """Return the package linked to a diagram, if any."""
        diagram_result = await self.db.execute(
            select(Diagram.knowledge_package_id).where(
                and_(
                    Diagram.id == diagram_id,
                    Diagram.user_id == self.user_id,
                    Diagram.is_deleted.is_(False),
                )
            )
        )
        package_id = diagram_result.scalar_one_or_none()
        if package_id:
            return await self.get_package(int(package_id))

        batch_result = await self.db.execute(
            select(DocumentBatch).where(
                and_(
                    DocumentBatch.user_id == self.user_id,
                    DocumentBatch.diagram_id == diagram_id,
                )
            )
        )
        return batch_result.scalars().first()

    async def find_doc_summary_package_for_diagram(
        self,
        diagram_id: str,
    ) -> Optional[DocumentBatch]:
        """Return a ``source=doc_summary`` package for the diagram, if any."""
        linked = await self.find_package_for_diagram(diagram_id)
        if linked is not None and linked.source == "doc_summary":
            return linked

        batch_result = await self.db.execute(
            select(DocumentBatch).where(
                and_(
                    DocumentBatch.user_id == self.user_id,
                    DocumentBatch.diagram_id == diagram_id,
                    DocumentBatch.source == "doc_summary",
                )
            )
        )
        return batch_result.scalars().first()

    @staticmethod
    def _doc_summary_package_matches_diagram(
        package: DocumentBatch,
        diagram_id: Optional[str],
    ) -> bool:
        """True when package is unbound or already linked to ``diagram_id``."""
        if not diagram_id or not package.diagram_id:
            return True
        return package.diagram_id == diagram_id

    async def ensure_doc_summary_session(
        self,
        diagram_id: Optional[str] = None,
        diagram_title: Optional[str] = None,
        package_id: Optional[int] = None,
        create_if_missing: bool = False,
    ) -> DocumentBatch:
        """Return the Document Summary package for a canvas session.

        Resumes an existing ``source=doc_summary`` package linked by ``package_id``
        or ``diagram_id``. Creates a new package only when ``create_if_missing``
        is true (first ingest). Never resumes a Knowledge Space / File Center package.
        Ignores a stale ``package_id`` that belongs to a different diagram so the
        session always tracks the active diagram's COS extract.
        """
        if package_id is not None:
            existing = await self.get_package(package_id)
            if not existing:
                raise ValueError(f"Package {package_id} not found or access denied")
            if existing.source != "doc_summary":
                raise ValueError("Package is not a Document Summary session")
            if self._doc_summary_package_matches_diagram(existing, diagram_id):
                if diagram_id and not existing.diagram_id:
                    return await self.update_package(existing.id, diagram_id=diagram_id)
                return existing
            logger.info(
                "[FileCenter] Ignoring stale doc_summary package_id=%s (linked to %s) for diagram=%s user=%s",
                package_id,
                existing.diagram_id,
                diagram_id,
                self.user_id,
            )

        if diagram_id:
            linked = await self.find_doc_summary_package_for_diagram(diagram_id)
            if linked:
                return linked

        if not create_if_missing:
            raise ValueError("No Document Summary package for this session")

        name = (diagram_title or "").strip() or "Untitled package"
        # Re-check immediately before insert to shrink the concurrent-create window.
        if diagram_id:
            linked = await self.find_doc_summary_package_for_diagram(diagram_id)
            if linked:
                return linked
        return await self.create_package(name=name, diagram_id=diagram_id, source="doc_summary")

    async def clear_doc_summary_session(
        self,
        *,
        diagram_id: Optional[str] = None,
        package_id: Optional[int] = None,
    ) -> bool:
        """Delete the Document Summary package for a canvas session (COS + Redis + DB).

        Resolves by ``package_id`` and/or ``diagram_id``. Returns True when a
        package was deleted. Safe no-op when nothing is linked.
        """
        if package_id is None and not diagram_id:
            raise ValueError("package_id or diagram_id is required")

        package: Optional[DocumentBatch] = None
        if package_id is not None:
            package = await self.get_package(package_id)
            if package is not None and package.source != "doc_summary":
                raise ValueError("Package is not a Document Summary session")
            if package is not None and not self._doc_summary_package_matches_diagram(package, diagram_id):
                logger.info(
                    "[FileCenter] Ignoring stale clear package_id=%s for diagram=%s user=%s",
                    package_id,
                    diagram_id,
                    self.user_id,
                )
                package = None

        if package is None and diagram_id:
            package = await self.find_doc_summary_package_for_diagram(diagram_id)

        if package is None:
            return False

        await self.delete_package(package.id)
        return True

    async def resolve_package_for_mindmap_generate(
        self,
        *,
        package_id: Optional[int] = None,
        diagram_id: Optional[str] = None,
    ) -> Optional[DocumentBatch]:
        """Resolve package for generate: prefer diagram's doc_summary (COS) extract.

        Stale ``package_id`` values that belong to another diagram are ignored so
        generation always reads the active diagram's markdown.
        """
        package: Optional[DocumentBatch] = None
        if package_id is not None:
            package = await self.get_package(package_id)
            if (
                package is not None
                and package.source == "doc_summary"
                and not self._doc_summary_package_matches_diagram(package, diagram_id)
            ):
                logger.info(
                    "[FileCenter] Ignoring stale generate package_id=%s for diagram=%s user=%s",
                    package_id,
                    diagram_id,
                    self.user_id,
                )
                package = None

        if package is None and diagram_id:
            package = await self.find_doc_summary_package_for_diagram(diagram_id)
            if package is None:
                package = await self.find_package_for_diagram(diagram_id)

        return package

    async def update_package(
        self,
        package_id: int,
        name: Optional[str] = None,
        diagram_id: Optional[str] = None,
    ) -> DocumentBatch:
        """Rename a package and/or (re)link it to a diagram."""
        package = await self.get_package(package_id)
        if not package:
            raise ValueError(f"Package {package_id} not found or access denied")

        if name is not None:
            package.name = name.strip()[:200] or package.name
        if diagram_id is not None:
            package.diagram_id = diagram_id
            if package.source != "doc_summary":
                await self._link_diagram_to_package(diagram_id, package.id)

        await self.db.commit()
        await self.db.refresh(package)
        return package

    async def get_package_documents(self, package_id: int) -> List[KnowledgeDocument]:
        """Return all sources belonging to a package (newest first)."""
        result = await self.db.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.batch_id == package_id)
            .order_by(KnowledgeDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def reindex_package_sections(self, package_id: int) -> Dict[str, Any]:
        """Queue full reprocessing for completed sources to refresh section metadata."""
        package = await self.get_package(package_id)
        if not package:
            raise ValueError(f"Package {package_id} not found or access denied")

        documents = await self.get_package_documents(package_id)
        completed = [doc for doc in documents if doc.status == "completed"]
        if not completed:
            return {"message": "No completed documents to reindex", "enqueued_ids": [], "count": 0}

        enqueued_ids: List[int] = []
        for document in completed:
            document.status = "pending"
            document.processing_progress = "queued"
            document.processing_progress_percent = 0
            document.error_message = None
            self.db.add(document)
            enqueued_ids.append(document.id)

        await self.db.commit()
        logger.info(
            "[FileCenter] Queued section reindex for package=%s docs=%s user=%s",
            package_id,
            enqueued_ids,
            self.user_id,
        )
        return {
            "message": f"Queued section reindex for {len(enqueued_ids)} document(s)",
            "enqueued_ids": enqueued_ids,
            "count": len(enqueued_ids),
        }

    async def get_package_stats(self, package_ids: List[int]) -> Dict[int, Dict[str, int]]:
        """Return live ``{package_id: {"total", "completed"}}`` source counts.

        File Center uploads index one document at a time and do not maintain the
        ``DocumentBatch`` completion counters, so the source counts are derived
        from the documents themselves in a single grouped query (avoids N+1).
        """
        if not package_ids:
            return {}
        result = await self.db.execute(
            select(
                KnowledgeDocument.batch_id,
                func.count(KnowledgeDocument.id),
                func.count(case((KnowledgeDocument.status == "completed", 1))),
            )
            .where(KnowledgeDocument.batch_id.in_(package_ids))
            .group_by(KnowledgeDocument.batch_id)
        )
        stats: Dict[int, Dict[str, int]] = {}
        for batch_id, total, completed in result.all():
            stats[batch_id] = {"total": int(total or 0), "completed": int(completed or 0)}
        return stats

    async def delete_package(self, package_id: int) -> None:
        """Delete a package and all of its sources (Qdrant + DB + files)."""
        package = await self.get_package(package_id)
        if not package:
            raise ValueError(f"Package {package_id} not found or access denied")

        documents = await self.get_package_documents(package_id)
        for document in documents:
            await self.ks.delete_document(document.id)

        # Detach any diagrams still pointing at this package.
        diagram_result = await self.db.execute(
            select(Diagram).where(
                and_(
                    Diagram.knowledge_package_id == package_id,
                    Diagram.user_id == self.user_id,
                )
            )
        )
        for diagram in diagram_result.scalars().all():
            diagram.knowledge_package_id = None

        await self.db.delete(package)
        await self.db.commit()

        # Remove the on-disk wiki layer (v2a), if any.
        package_wiki_store.delete_wiki(self.user_id, package_id)

        logger.info("[FileCenter] Deleted package %s for user %s", package_id, self.user_id)

    async def attach_document(self, document_id: int, package_id: int) -> KnowledgeDocument:
        """Attach an already-uploaded document to a package."""
        package = await self.get_package(package_id)
        if not package:
            raise ValueError(f"Package {package_id} not found or access denied")

        document = await self.ks.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found or access denied")

        document.batch_id = package_id
        await self.db.commit()
        await self.db.refresh(document)
        return document

    async def find_document_by_url(self, package_id: int, page_url: str) -> Optional[KnowledgeDocument]:
        """Return an existing source in the package with the same page URL, if any."""
        if not page_url:
            return None
        documents = await self.get_package_documents(package_id)
        for document in documents:
            meta = document.doc_metadata or {}
            if meta.get("page_url") == page_url:
                return document
        return None

    async def add_text_source(
        self,
        package_id: int,
        content: str,
        title: str,
        source_kind: str = "paste",
        page_url: Optional[str] = None,
        language: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeDocument:
        """Create a markdown source from pasted text or web content in a package.

        The text is written to disk as a ``.md`` file and registered as a
        ``KnowledgeDocument`` linked to the package. Indexing is started later
        via ``/packages/{id}/documents/start-processing`` (e.g. on Generate).
        """
        package = await self.get_package(package_id)
        if not package:
            raise ValueError(f"Package {package_id} not found or access denied")

        text = (content or "").strip()
        if not text:
            raise ValueError("Cannot ingest empty content")

        await self._enforce_quota()
        space = await self.ks.create_knowledge_space()

        file_name = await self._unique_file_name(space.id, title, source_kind)
        encoded = text.encode("utf-8")

        document = KnowledgeDocument(
            space_id=space.id,
            file_name=file_name,
            file_path="",
            file_type=TEXT_SOURCE_FILE_TYPE,
            file_size=len(encoded),
            status="pending",
            batch_id=package_id,
            language=language,
            doc_metadata=self._build_text_metadata(source_kind, title, page_url, extra_metadata),
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        user_dir = self.ks.storage_dir / str(self.user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        final_path = ensure_within_directory(user_dir / f"{document.id}_{file_name}", user_dir)
        final_path.write_bytes(encoded)
        document.file_path = str(final_path)
        await self.db.commit()
        await self.db.refresh(document)

        logger.info(
            "[FileCenter] Added text source doc_id=%s package=%s kind=%s user=%s",
            document.id,
            package_id,
            source_kind,
            self.user_id,
        )
        return document

    async def resolve_diagram_rag_scope(self, diagram_id: str) -> Optional[PackageRagScope]:
        """Resolve the completed document IDs that scope RAG for a diagram.

        Returns ``None`` when the diagram has no linked package (whole-library
        fallback decided by the caller).
        """
        return await resolve_diagram_rag_scope(self.db, self.user_id, diagram_id)

    async def _link_diagram_to_package(self, diagram_id: str, package_id: int) -> None:
        """Best-effort: set diagrams.knowledge_package_id for an owned diagram."""
        result = await self.db.execute(
            select(Diagram).where(
                and_(
                    Diagram.id == diagram_id,
                    Diagram.user_id == self.user_id,
                )
            )
        )
        diagram = result.scalars().first()
        if diagram and diagram.knowledge_package_id != package_id:
            diagram.knowledge_package_id = package_id
            await self.db.commit()

    async def _enforce_quota(self) -> None:
        space = await self.ks.create_knowledge_space()
        result = await self.db.execute(
            select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.space_id == space.id)
        )
        count = result.scalar_one()
        if count >= self.ks.max_documents:
            raise ValueError(f"Maximum {self.ks.max_documents} documents allowed. Please delete a source first.")

    async def _unique_file_name(self, space_id: int, title: str, source_kind: str) -> str:
        base = _slugify_title(title, fallback=source_kind or "source")
        candidate = f"{base}.md"
        suffix = 1
        while await self._file_name_exists(space_id, candidate):
            candidate = f"{base}_{suffix}.md"
            suffix += 1
        return candidate

    async def _file_name_exists(self, space_id: int, file_name: str) -> bool:
        result = await self.db.execute(
            select(KnowledgeDocument.id).where(
                and_(
                    KnowledgeDocument.space_id == space_id,
                    KnowledgeDocument.file_name == file_name,
                )
            )
        )
        return result.scalars().first() is not None

    @staticmethod
    def _build_text_metadata(
        source_kind: str,
        title: str,
        page_url: Optional[str],
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {"ingest_source": source_kind}
        if title:
            metadata["page_title"] = title
        if page_url:
            metadata["page_url"] = page_url
        if extra_metadata:
            for key, value in extra_metadata.items():
                if value is not None:
                    metadata[key] = value
        return metadata
