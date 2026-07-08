from app.config import Settings
from app.core.document_source.base import DocumentSource
from app.ingestion.loaders import SUPPORTED_EXTENSIONS


def get_document_source(settings: Settings) -> DocumentSource:
    """
    Return a DocumentSource based on settings.document_source_backend.

    To add a new source (GCS, Azure Blob, ShareFile, SmartVault, ...):
      1. Implement DocumentSource in core/document_source/<name>_source.py
      2. Add a branch here
      3. Set DOCUMENT_SOURCE_BACKEND=<name> in .env
    """
    backend = settings.document_source_backend.lower()

    if backend == "local":
        from app.core.document_source.local_source import LocalDirSource
        return LocalDirSource(directory=settings.documents_dir, extensions=SUPPORTED_EXTENSIONS)

    if backend == "s3":
        from app.core.document_source.s3_source import S3Source
        return S3Source(
            bucket=settings.s3_bucket,
            prefix=settings.s3_prefix,
            extensions=SUPPORTED_EXTENSIONS,
            region=settings.s3_region,
        )

    raise ValueError(f"Unsupported document source backend: {backend!r}")
