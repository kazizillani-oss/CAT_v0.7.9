"""CAT Universal File Preview Engine — Viewer Registry (calc_terminal/viewers/registry.py).

Centralized file-type detector and viewer provider registry:
- Prevents files from being inappropriately opened as raw extracted text.
- Dispatches each file to its dedicated high-fidelity visual viewer.
- Extensible: plugins and extensions can register custom viewer providers.
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional, Set


class ViewerProvider:
    """Interface for a file preview/viewer provider."""

    def __init__(self, id: str, name: str, extensions: Set[str],
                 factory: Optional[Callable[[str, Any], Any]] = None) -> None:
        self.id = id
        self.name = name
        self.extensions = {ext.lower() if ext.startswith(".") else f".{ext.lower()}" for ext in extensions}
        self.factory = factory

    def can_open(self, file_path: str) -> bool:
        ext = os.path.splitext(str(file_path).lower())[1]
        return ext in self.extensions

    def create_viewer(self, file_path: str, **kwargs) -> Any:
        if self.factory is not None:
            return self.factory(file_path, **kwargs)
        raise NotImplementedError(f"Provider {self.id} has no factory implementation.")


class ViewerRegistry:
    """Registry coordinating all visual file viewers."""

    def __init__(self) -> None:
        self._providers: Dict[str, ViewerProvider] = {}
        self._register_builtins()

    def register(self, provider: ViewerProvider) -> None:
        """Register a new viewer provider."""
        self._providers[provider.id] = provider

    def unregister(self, provider_id: str) -> None:
        """Unregister a viewer provider."""
        self._providers.pop(provider_id, None)

    def get_provider(self, provider_id: str) -> Optional[ViewerProvider]:
        return self._providers.get(provider_id)

    def get_provider_for_file(self, file_path: str) -> Optional[ViewerProvider]:
        """Find the registered viewer provider capable of opening this file."""
        ext = os.path.splitext(str(file_path).lower())[1]
        for p in self._providers.values():
            if p.can_open(file_path):
                return p
        return None

    def can_open_visually(self, file_path: str) -> bool:
        """Return True if a specialized visual viewer exists for this file."""
        p = self.get_provider_for_file(file_path)
        return p is not None and p.id != "code"

    def create_viewer_for_file(self, file_path: str, **kwargs) -> Optional[Any]:
        """Create the appropriate viewer widget for the given file."""
        provider = self.get_provider_for_file(file_path)
        if provider:
            return provider.create_viewer(file_path, **kwargs)
        return None

    def _register_builtins(self) -> None:
        """Register default visual providers: image, pdf, docx, pptx, xlsx, csv."""
        # 1. Images
        image_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp", ".ico", ".tiff"}
        def _image_factory(path, **kwargs):
            from .image_viewer import ImageViewer
            return ImageViewer(path, **kwargs)
        self.register(ViewerProvider("image", "Image Viewer", image_exts, _image_factory))

        # 2. PDF
        pdf_exts = {".pdf"}
        def _pdf_factory(path, **kwargs):
            from .pdf_viewer import PdfViewer
            return PdfViewer(path, **kwargs)
        self.register(ViewerProvider("pdf", "PDF Document Viewer", pdf_exts, _pdf_factory))

        # 3. DOCX Document
        docx_exts = {".docx"}
        def _docx_factory(path, **kwargs):
            from .document_viewer import DocumentViewer
            return DocumentViewer(path, **kwargs)
        self.register(ViewerProvider("document", "DOCX Document Viewer", docx_exts, _docx_factory))

        # 4. PPTX Presentation
        pptx_exts = {".pptx"}
        def _pptx_factory(path, **kwargs):
            from .presentation_viewer import PresentationViewer
            return PresentationViewer(path, **kwargs)
        self.register(ViewerProvider("presentation", "Presentation Slide Viewer", pptx_exts, _pptx_factory))

        # 5. Spreadsheets (XLSX, CSV)
        sheet_exts = {".xlsx", ".csv"}
        def _sheet_factory(path, **kwargs):
            from .spreadsheet_viewer import SpreadsheetViewer
            return SpreadsheetViewer(path, **kwargs)
        self.register(ViewerProvider("spreadsheet", "Spreadsheet Grid Viewer", sheet_exts, _sheet_factory))


# Global singleton registry
_GLOBAL_VIEWER_REGISTRY: Optional[ViewerRegistry] = None


def get_viewer_registry() -> ViewerRegistry:
    """Return the global ViewerRegistry singleton."""
    global _GLOBAL_VIEWER_REGISTRY
    if _GLOBAL_VIEWER_REGISTRY is None:
        _GLOBAL_VIEWER_REGISTRY = ViewerRegistry()
    return _GLOBAL_VIEWER_REGISTRY
