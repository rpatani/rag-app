"""
DocumentSource interface.

Where documents come from is a pluggable domain, exactly like the vector
store, embedder, and LLM. Every backend (local directory, S3, GCS, a client
portal, ...) implements this interface; the ingestion pipeline depends only
on it. Adding a new source = implement the interface, add a factory branch,
set DOCUMENT_SOURCE_BACKEND.

The key design decision: `fetch()` returns a *local file path*. Loaders and
OCR never need to know where a document came from — remote sources download
to a temp file, local sources return the file in place.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SourceDocument:
    """A document as enumerated by a source, before it is fetched."""

    name: str            # filename, e.g. "policy.pdf"
    uri: str             # stable identity, e.g. "/data/documents/policy.pdf" or "s3://bucket/key"
    size: int | None = None
    version: str | None = None  # source-native version (ETag, mtime fingerprint); None = unknown


class DocumentSource(ABC):
    @abstractmethod
    def list_documents(self) -> list[SourceDocument]:
        """Enumerate ingestable documents (already filtered to supported types)."""
        raise NotImplementedError

    @abstractmethod
    def fetch(self, doc: SourceDocument) -> Path:
        """Make the document available as a local file and return its path."""
        raise NotImplementedError

    def cleanup(self, doc: SourceDocument, local_path: Path) -> None:
        """Release any resources created by fetch(). Default: nothing.

        Remote sources override this to delete the temp file they downloaded;
        the local source must NOT delete the original file, so the default
        is a no-op.
        """
