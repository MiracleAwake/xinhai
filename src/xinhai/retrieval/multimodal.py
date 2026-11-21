"""Interfaces for visual and mixed-modality retrieval; implementations are optional."""
from dataclasses import dataclass

@dataclass(frozen=True)
class MultimodalAsset:
    asset_ref: str
    modality: str = 'image'
    ocr_text: str = ''
    visual_summary: str = ''

class VisualEmbeddingProvider:
    def embed_image(self, asset_ref: str) -> list[float]:
        raise NotImplementedError

class UnavailableVisualEmbedding(VisualEmbeddingProvider):
    def embed_image(self, asset_ref: str) -> list[float]:
        return []
