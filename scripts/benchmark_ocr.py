"""Benchmark local TrOCR against a CSV of manually transcribed handwriting."""

import argparse
import csv
import statistics
import tempfile
import threading
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.ocr.benchmark import error_rates
from app.services.ocr.lines import segment_lines
from app.services.ocr.trocr import TrOCRProvider
import psutil


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="CSV with image and transcription columns")
    parser.add_argument("--image-column", default="image")
    parser.add_argument("--text-column", default="transcription")
    parser.add_argument("--limit", type=int, help="Run only the first N rows (useful for quick smoke benchmarks)")
    args = parser.parse_args()
    with args.dataset.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if args.limit is not None:
        rows = rows[:max(0, args.limit)]
    if not rows:
        raise SystemExit("Dataset is empty; no accuracy figures were generated.")
    provider = TrOCRProvider()
    cer_values, wer_values, seconds = [], [], []
    process = psutil.Process()
    peak_rss = [process.memory_info().rss]
    stop_sampler = threading.Event()

    def sample_memory():
        while not stop_sampler.wait(.1):
            peak_rss[0] = max(peak_rss[0], process.memory_info().rss)

    sampler = threading.Thread(target=sample_memory, daemon=True)
    sampler.start()
    try:
        with tempfile.TemporaryDirectory(prefix="sfd-benchmark-") as temp:
            for index, row in enumerate(rows, 1):
                image = (args.dataset.parent / row[args.image_column]).resolve()
                ground_truth = row[args.text_column]
                with tempfile.TemporaryDirectory(dir=temp) as out:
                    lines = segment_lines(image, Path(out))
                    start = time.perf_counter()
                    recognized = " ".join(provider.recognize_line(line.path).normalized_text for line in lines)
                    seconds.append(time.perf_counter() - start)
                cer, wer = error_rates(ground_truth, recognized)
                cer_values.append(cer); wer_values.append(wer)
                print(f"{index}/{len(rows)} CER={cer:.4f} WER={wer:.4f} seconds={seconds[-1]:.2f}")
    finally:
        stop_sampler.set(); sampler.join(timeout=1)
        peak_rss[0] = max(peak_rss[0], process.memory_info().rss)
    print(f"Samples: {len(rows)}")
    print(f"Mean CER: {statistics.mean(cer_values):.4f}")
    print(f"Mean WER: {statistics.mean(wer_values):.4f}")
    print(f"Mean processing seconds/sample: {statistics.mean(seconds):.2f}")
    print(f"Peak process RSS: {peak_rss[0] / (1024 * 1024):.1f} MiB")


if __name__ == "__main__":
    main()
