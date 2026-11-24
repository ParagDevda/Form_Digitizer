"""One-time, explicit model provisioning. Runtime OCR never invokes this script."""

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=Path("backend/models/trocr-base-handwritten"))
    args = parser.parse_args()
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise SystemExit("Install backend/requirements-ocr-hf.txt before provisioning the model") from exc
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id="microsoft/trocr-base-handwritten",
        local_dir=destination,
        # The repository mirrors the same 1.33 GB weights in both .bin and
        # .safetensors formats. The safe-tensors copy is sufficient and avoids
        # downloading the duplicate pickle checkpoint.
        allow_patterns=["config.json", "generation_config.json", "preprocessor_config.json", "special_tokens_map.json", "tokenizer_config.json", "vocab.json", "merges.txt", "model.safetensors"],
    )
    print(f"Model weights saved to {destination}")


if __name__ == "__main__":
    main()
