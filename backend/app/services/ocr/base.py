"""Stable OCR provider contract, independent of the chosen model."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Recognition:
    raw_text: str
    normalized_text: str
    model: str
    confidence: float | None = None
    warnings: tuple[str, ...] = ()


class OCRProvider(ABC):
    @abstractmethod
    def recognize_line(self, image: Path) -> Recognition:
        """Recognize one cropped text line from a local image."""

