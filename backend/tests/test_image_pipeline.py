import cv2
import numpy as np
import pytest

from app.services.image_processing.images import align_to_template, crop_region, preprocess
from app.services.ocr.benchmark import error_rates
from app.services.ocr.lines import segment_lines
from app.services.ocr.trocr import TrOCRProvider


def test_line_segmentation_and_preprocessing(tmp_path):
    image = np.full((600, 800, 3), 255, dtype=np.uint8)
    cv2.putText(image, "First handwritten line", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    cv2.putText(image, "Second handwritten line", (30, 360), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
    path = tmp_path / "lines.png"
    cv2.imwrite(str(path), image)
    lines = segment_lines(path, tmp_path / "crops")
    assert len(lines) == 2
    assert all(line.path.is_file() for line in lines)
    assert preprocess(image).shape == (600, 800)
    assert crop_region(image, (.1, .1, .5, .5)).shape[:2] == (300, 400)


def test_blank_answer_region_does_not_create_an_ocr_line(tmp_path):
    blank = np.full((80, 500, 3), 255, dtype=np.uint8)
    path = tmp_path / "blank.png"
    cv2.imwrite(str(path), blank)
    assert segment_lines(path, tmp_path / "blank-crops") == []


def test_template_feature_alignment(tmp_path):
    template = np.full((900, 650, 3), 255, dtype=np.uint8)
    for y in range(100, 800, 90):
        cv2.putText(template, f"Printed question number {y}", (35, y), cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 0, 0), 2)
        cv2.line(template, (30, y + 15), (600, y + 15), (0, 0, 0), 1)
    angle = cv2.getPerspectiveTransform(np.float32([[0, 0], [649, 0], [649, 899], [0, 899]]), np.float32([[20, 10], [620, 0], [640, 890], [0, 850]]))
    photographed = cv2.warpPerspective(template, angle, (660, 910))
    aligned = align_to_template(photographed, template)
    assert aligned.shape == template.shape


def test_error_rate_and_offline_model_failure(tmp_path):
    assert error_rates("hello world", "hello word") == (1 / 11, .5)
    provider = TrOCRProvider(tmp_path / "missing")
    with pytest.raises(RuntimeError, match="Local TrOCR model not found"):
        provider.recognize_line(tmp_path / "line.png")
