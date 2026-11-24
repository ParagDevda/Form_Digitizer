"""Local image and PDF decoding, preprocessing, perspective correction, and crops."""

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps


def load_image(path: Path, max_dimension: int = 2400) -> np.ndarray:
    """Load an image with EXIF orientation applied and cap memory use."""
    try:
        with Image.open(path) as opened:
            rgb = ImageOps.exif_transpose(opened).convert("RGB")
            scale = min(1.0, max_dimension / max(rgb.size))
            if scale < 1:
                rgb = rgb.resize((round(rgb.width * scale), round(rgb.height * scale)), Image.Resampling.LANCZOS)
            return cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read image file: {path.name}") from exc


def preprocess(image: np.ndarray, threshold: bool = False) -> np.ndarray:
    """Mild denoise and CLAHE contrast enhancement; thresholding stays opt-in."""
    if image is None or image.size == 0:
        raise ValueError("Image is empty")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    denoised = cv2.fastNlMeansDenoising(gray, None, h=5, templateWindowSize=7, searchWindowSize=21)
    enhanced = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8)).apply(denoised)
    if threshold:
        return cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12)
    return enhanced


def correct_document_perspective(image: np.ndarray) -> tuple[np.ndarray, bool]:
    """Correct a strong four-corner page contour; otherwise return the original."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:8]
    corners = None
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) == 4 and cv2.contourArea(polygon) > image.shape[0] * image.shape[1] * 0.2:
            corners = polygon.reshape(4, 2).astype("float32")
            break
    if corners is None:
        return image, False
    sums = corners.sum(axis=1)
    diffs = np.diff(corners, axis=1).ravel()
    ordered = np.array([corners[np.argmin(sums)], corners[np.argmin(diffs)], corners[np.argmax(sums)], corners[np.argmax(diffs)]], dtype="float32")
    tl, tr, br, bl = ordered
    width = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
    height = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
    if width < 100 or height < 100:
        return image, False
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
    matrix = cv2.getPerspectiveTransform(ordered, target)
    return cv2.warpPerspective(image, matrix, (width, height)), True


def align_to_template(image: np.ndarray, template: np.ndarray, min_inliers: int = 12) -> np.ndarray:
    """Feature-align a photographed page to its blank sample or fail explicitly."""
    def resized_gray(frame: np.ndarray) -> tuple[np.ndarray, float]:
        scale = min(1.0, 1400 / max(frame.shape[:2]))
        resized = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else frame
        return cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY), scale

    source_gray, source_scale = resized_gray(image)
    target_gray, target_scale = resized_gray(template)
    detector = cv2.AKAZE_create()
    source_points, source_desc = detector.detectAndCompute(source_gray, None)
    target_points, target_desc = detector.detectAndCompute(target_gray, None)
    if source_desc is None or target_desc is None or len(source_desc) < min_inliers or len(target_desc) < min_inliers:
        raise ValueError("Template alignment failed: not enough printed page features. Review and adjust regions manually.")
    matches = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(source_desc, target_desc, k=2)
    good = [first for first, second in matches if first.distance < 0.72 * second.distance]
    if len(good) < min_inliers:
        raise ValueError("Template alignment failed: sample and document do not match reliably.")
    src = np.float32([source_points[m.queryIdx].pt for m in good]).reshape(-1, 1, 2) / source_scale
    dst = np.float32([target_points[m.trainIdx].pt for m in good]).reshape(-1, 1, 2) / target_scale
    matrix, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    inliers = int(mask.sum()) if mask is not None else 0
    if matrix is None or inliers < min_inliers:
        raise ValueError("Template alignment failed: geometric verification was not reliable.")
    aligned = cv2.warpPerspective(image, matrix, (template.shape[1], template.shape[0]))
    if aligned.size == 0:
        raise ValueError("Template alignment failed while transforming the page.")
    return aligned


def crop_region(image: np.ndarray, region: tuple[float, float, float, float]) -> np.ndarray:
    """Crop normalized x/y/width/height coordinates with bounds checking."""
    x, y, width, height = region
    if not (0 <= x < 1 and 0 <= y < 1 and width > 0 and height > 0 and x + width <= 1 and y + height <= 1):
        raise ValueError("Answer region coordinates are outside the page")
    h, w = image.shape[:2]
    crop = image[round(y * h):round((y + height) * h), round(x * w):round((x + width) * w)]
    if crop.size == 0:
        raise ValueError("Answer region produced an empty crop")
    return crop


def render_pdf(path: Path, output_dir: Path, dpi: int = 180, max_pages: int = 100) -> list[Path]:
    """Render PDF pages independently and cap accidental huge documents."""
    import fitz

    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with fitz.open(path) as document:
            if document.page_count == 0 or document.page_count > max_pages:
                raise ValueError(f"PDF page count must be between 1 and {max_pages}")
            scale = dpi / 72
            outputs = []
            for index, page in enumerate(document):
                pixel_width, pixel_height = page.rect.width * scale, page.rect.height * scale
                if pixel_width > 7000 or pixel_height > 7000 or pixel_width * pixel_height > 40_000_000:
                    raise ValueError("PDF page dimensions exceed the supported processing limit")
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                target = output_dir / f"page-{index + 1:03d}.png"
                pixmap.save(target)
                outputs.append(target)
            return outputs
    except (fitz.FileDataError, RuntimeError) as exc:
        raise ValueError(f"Cannot read PDF file: {path.name}") from exc
