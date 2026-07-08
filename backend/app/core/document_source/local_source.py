from pathlib import Path

from app.core.document_source.base import DocumentSource, SourceDocument


class LocalDirSource(DocumentSource):
    """Documents from a directory on the local filesystem (the appliance default)."""

    def __init__(self, directory: str, extensions: set[str]):
        self.directory = Path(directory)
        self.extensions = extensions

    def list_documents(self) -> list[SourceDocument]:
        if not self.directory.exists():
            return []

        docs: list[SourceDocument] = []
        for path in sorted(self.directory.iterdir()):
            if not path.is_file() or path.suffix.lower() not in self.extensions:
                continue
            stat = path.stat()
            docs.append(
                SourceDocument(
                    name=path.name,
                    uri=str(path),
                    size=stat.st_size,
                    version=f"{stat.st_mtime_ns}:{stat.st_size}",
                )
            )
        return docs

    def fetch(self, doc: SourceDocument) -> Path:
        return Path(doc.uri)
