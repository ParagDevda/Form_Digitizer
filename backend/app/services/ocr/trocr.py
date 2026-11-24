"""CPU TrOCR provider. Weights must be provisioned locally before use."""

import os
import threading
from pathlib import Path

from app.services.ocr.base import OCRProvider, Recognition

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


class TrOCRProvider(OCRProvider):
    def __init__(self, model_path: str | Path | None = None) -> None:
        default_path = Path(__file__).resolve().parents[4] / "backend" / "models" / "trocr-base-handwritten"
        self.model_path = Path(model_path or os.environ.get("STUDENT_DIGITIZER_TROCR_PATH", default_path)).resolve()
        self._processor = None
        self._model = None
        self._lock = threading.Lock()

    def _load(self) -> None:
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            if not self.model_path.is_dir():
                raise RuntimeError(f"Local TrOCR model not found at {self.model_path}. Run the one-time model setup first.")
            try:
                import torch
                from transformers import TrOCRProcessor, VisionEncoderDecoderModel
            except ImportError as exc:
                raise RuntimeError("TrOCR dependencies are not installed. Install the OCR requirements during setup.") from exc
            self._processor = TrOCRProcessor.from_pretrained(str(self.model_path), local_files_only=True, use_fast=False)
            self._model = VisionEncoderDecoderModel.from_pretrained(str(self.model_path), local_files_only=True).to("cpu").eval()

    def recognize_line(self, image: Path) -> Recognition:
        self._load()
        from PIL import Image
        import torch

        with Image.open(image) as opened:
            pixels = self._processor(images=opened.convert("RGB"), return_tensors="pt").pixel_values
        with torch.inference_mode():
            generated = self._model.generate(pixels, output_scores=True, return_dict_in_generate=True)
        text = self._processor.batch_decode(generated.sequences, skip_special_tokens=True)[0]
        normalized = " ".join(text.split())
        confidence = None
        if generated.scores:
            token_scores = self._model.compute_transition_scores(generated.sequences, generated.scores, normalize_logits=True)
            confidence = float(token_scores[0].exp().mean().item())
        return Recognition(raw_text=text, normalized_text=normalized, model="microsoft/trocr-base-handwritten", confidence=confidence)
