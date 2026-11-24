"""Download a small labeled IAM-line test subset for a reproducible local benchmark."""

import argparse
import csv
from pathlib import Path

from datasets import load_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=50)
    parser.add_argument("--output", type=Path, default=Path("local_data/benchmark/iam-line-test"))
    args = parser.parse_args()
    if not 1 <= args.samples <= 1000:
        raise SystemExit("Choose between 1 and 1000 samples")
    args.output.mkdir(parents=True, exist_ok=True)
    rows = load_dataset("ianua/IAM-line", split=f"test[:{args.samples}]")
    with (args.output / "ground-truth.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image", "transcription"])
        writer.writeheader()
        for index, row in enumerate(rows, 1):
            filename = f"line-{index:04d}.png"
            row["image"].convert("RGB").save(args.output / filename)
            writer.writerow({"image": filename, "transcription": row["text"]})
    (args.output / "PROVENANCE.txt").write_text(
        "Dataset: ianua/IAM-line (Hugging Face Datasets)\n"
        "Split: test\n"
        "License shown by dataset card: MIT\n"
        "Subset: first selected test rows; images and transcripts are stored locally.\n"
        "Source: https://huggingface.co/datasets/ianua/IAM-line\n",
        encoding="utf-8",
    )
    print(f"Prepared {len(rows)} labeled handwriting lines in {args.output.resolve()}")


if __name__ == "__main__":
    main()
