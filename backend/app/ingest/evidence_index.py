"""Evidence Indexing module (FR-2, FR-3, FR-16, Hard Rule 4)."""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """Metadata for an indexed piece of evidence."""
    evidence_id: str
    case_id: str
    file_path: Path
    media_type: str  # e.g., 'image/png', 'text/plain', 'application/json'
    content_hash: str
    is_missing: bool = False
    error_message: Optional[str] = None


class EvidenceIndex:
    """In-memory and persistent index of evidence media mapped by case_id."""

    def __init__(self):
        self.by_evidence_id: Dict[str, EvidenceItem] = {}
        self.by_case_id: Dict[str, List[EvidenceItem]] = {}

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Compute SHA-256 hash of a file for deterministic caching and verification."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def register_item(
        self,
        evidence_id: str,
        case_id: str,
        file_path: Path,
        media_type: Optional[str] = None,
    ) -> EvidenceItem:
        """Register an evidence item into the index, computing hash and checking existence."""
        if not file_path.exists():
            item = EvidenceItem(
                evidence_id=evidence_id,
                case_id=case_id,
                file_path=file_path,
                media_type=media_type or "unknown",
                content_hash="",
                is_missing=True,
                error_message=f"File not found: {file_path}",
            )
        else:
            try:
                content_hash = self.compute_sha256(file_path)
                inferred_type = media_type or self._infer_media_type(file_path)
                item = EvidenceItem(
                    evidence_id=evidence_id,
                    case_id=case_id,
                    file_path=file_path,
                    media_type=inferred_type,
                    content_hash=content_hash,
                    is_missing=False,
                )
            except Exception as e:
                item = EvidenceItem(
                    evidence_id=evidence_id,
                    case_id=case_id,
                    file_path=file_path,
                    media_type=media_type or "unknown",
                    content_hash="",
                    is_missing=True,
                    error_message=str(e),
                )

        self.by_evidence_id[evidence_id] = item
        self.by_case_id.setdefault(case_id, []).append(item)
        return item

    def get_evidence_for_case(self, case_id: str) -> List[EvidenceItem]:
        """Retrieve all evidence registered for a given case."""
        return self.by_case_id.get(case_id, [])

    def get_item(self, evidence_id: str) -> Optional[EvidenceItem]:
        """Retrieve a single evidence item by ID."""
        return self.by_evidence_id.get(evidence_id)

    def validate_citations(self, case_id: str, citations: List[str]) -> Tuple[bool, List[str]]:
        """
        Validate that every citation ID:
        1. Exists in the index.
        2. Belongs to the specific case_id.
        Returns (is_valid, list_of_invalid_or_foreign_ids).
        """
        invalid_ids = []
        for cid in citations:
            item = self.by_evidence_id.get(cid)
            if item is None or item.case_id != case_id:
                invalid_ids.append(cid)
        return len(invalid_ids) == 0, invalid_ids

    @staticmethod
    def _infer_media_type(path: Path) -> str:
        """Infer standard media type from extension."""
        suffix = path.suffix.lower()
        if suffix in [".png"]:
            return "image/png"
        elif suffix in [".jpg", ".jpeg"]:
            return "image/jpeg"
        elif suffix in [".json"]:
            return "application/json"
        elif suffix in [".log", ".txt"]:
            return "text/plain"
        elif suffix in [".csv"]:
            return "text/csv"
        elif suffix in [".pdf"]:
            return "application/pdf"
        return "application/octet-stream"
