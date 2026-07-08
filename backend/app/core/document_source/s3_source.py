"""
S3 document source.

Credentials are NEVER stored in app config: boto3 resolves them through its
standard chain (environment variables, shared credentials file, IAM
instance/task role). The app only knows bucket, optional key prefix, and
optional region.

Security notes:
- Object keys are used only to derive a safe local temp filename via
  Path(...).name — a hostile key like "a/../../etc/cron.d/x" cannot escape
  the temp directory.
- Downloads go to a private temp dir and are deleted after ingestion
  (cleanup()), so remote content does not accumulate on local disk.
"""

import logging
import tempfile
from pathlib import Path

from app.core.document_source.base import DocumentSource, SourceDocument

logger = logging.getLogger(__name__)


class S3Source(DocumentSource):
    def __init__(
        self,
        bucket: str,
        prefix: str,
        extensions: set[str],
        region: str = "",
        client=None,  # injectable for tests
    ):
        if not bucket:
            raise ValueError("S3 source requires a bucket name (set S3_BUCKET).")
        self.bucket = bucket
        self.prefix = prefix
        self.extensions = extensions

        if client is not None:
            self._client = client
        else:
            import boto3  # lazy: only needed when this backend is selected

            self._client = boto3.client("s3", region_name=region or None)

    def list_documents(self) -> list[SourceDocument]:
        docs: list[SourceDocument] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                name = Path(key).name
                if not name or Path(name).suffix.lower() not in self.extensions:
                    continue
                docs.append(
                    SourceDocument(
                        name=name,
                        uri=f"s3://{self.bucket}/{key}",
                        size=obj.get("Size"),
                        version=(obj.get("ETag") or "").strip('"') or None,
                    )
                )
        return docs

    def fetch(self, doc: SourceDocument) -> Path:
        key = doc.uri.removeprefix(f"s3://{self.bucket}/")
        # Safe local name: strip any path components from the key.
        tmp_dir = Path(tempfile.mkdtemp(prefix="rag_s3_"))
        local_path = tmp_dir / Path(doc.name).name
        logger.info("Fetching %s (%s bytes)", doc.uri, doc.size)
        self._client.download_file(self.bucket, key, str(local_path))
        return local_path

    def cleanup(self, doc: SourceDocument, local_path: Path) -> None:
        try:
            local_path.unlink(missing_ok=True)
            local_path.parent.rmdir()
        except OSError:
            logger.warning("Could not remove temp file %s", local_path)
