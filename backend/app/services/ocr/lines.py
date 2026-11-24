"""Projection-profile line segmentation with an explicit whole-region fallback."""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class LineCrop:
    path: Path
    y: int
    height: int
    fallback: bool = False


def segment_lines(image_path: Path, output_dir: Path, min_height: int = 8, gap_tolerance: int = 5) -> list[LineCrop]:
    """Segment horizontally separated handwriting lines without fixed strip slicing."""
    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image: {image_path}")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 12)
    projection = np.count_nonzero(ink, axis=1)
    active = projection > max(1, int(image.shape[1] * 0.002))
    spans: list[tuple[int, int]] = []
    start = None
    gap = 0
    for y, is_active in enumerate(active):
        if is_active:
            if start is None:
                start = y
            gap = 0
        elif start is not None:
            gap += 1
            if gap > gap_tolerance:
                end = y - gap + 1
                if end - start >= min_height:
                    spans.append((start, end))
                start = None
                gap = 0
    if start is not None and image.shape[0] - start >= min_height:
        spans.append((start, image.shape[0]))

    output_dir.mkdir(parents=True, exist_ok=True)
    if not spans:
        ink_pixels = int(np.count_nonzero(ink))
        if ink_pixels < max(8, int(image.shape[0] * image.shape[1] * 0.0001)):
            return []
        target = output_dir / "line-001.png"
        if not cv2.imwrite(str(target), image):
            raise OSError(f"Could not write line crop: {target}")
        return [LineCrop(target, 0, image.shape[0], fallback=True)]
    margin = max(2, int(image.shape[0] * 0.01))
    lines = []
    for index, (top, bottom) in enumerate(spans, 1):
        top = max(0, top - margin)
        bottom = min(image.shape[0], bottom + margin)
        target = output_dir / f"line-{index:03d}.png"
        if not cv2.imwrite(str(target), image[top:bottom, :]):
            raise OSError(f"Could not write line crop: {target}")
        lines.append(LineCrop(target, top, bottom - top))
    return lines
