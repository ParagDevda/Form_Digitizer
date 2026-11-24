# TrOCR CPU benchmark

## Dataset and method

- Dataset: [`ianua/IAM-line`](https://huggingface.co/datasets/ianua/IAM-line), whose card lists English handwritten line images, transcriptions, and an MIT license.
- Split: `test`.
- Evaluation subset: first 50 rows, saved locally under `local_data/benchmark/iam-line-test/` by `scripts/prepare_iam_benchmark.py`.
- Model: `microsoft/trocr-base-handwritten`, loaded from the locally stored safetensors checkpoint.
- Runtime: PyTorch CPU build, Python 3.12, Transformers 4.52.4. No CUDA used.
- Metrics: case-sensitive character edit distance divided by reference character count (CER); case-folded word edit distance divided by reference word count (WER), with punctuation excluded from word tokens.

## Results

| Measure | Result |
|---|---:|
| Test lines | 50 |
| Mean CER | 0.0816 |
| Mean WER | 0.1823 |
| Mean time per line | 8.11 s |
| Peak process RSS | 1,763.6 MiB |

CER, WER, and mean time came from one 50-sample run. Its first sample took 53.97 seconds because it loaded the model; subsequent samples averaged about 7.2 seconds. Peak RSS came from a separate 10-sample run that included model loading. These are line-image results on the IAM test partition, not results on student questionnaire photographs. The first 50 rows are a small subset, not a statistically comprehensive study.

## Reproduction

```powershell
python -m pip install -r backend\requirements-benchmark.txt
python scripts\prepare_iam_benchmark.py --samples 50
.\.venv\Scripts\python.exe scripts\benchmark_ocr.py local_data\benchmark\iam-line-test\ground-truth.csv
```

The public benchmark images and transcripts stay under ignored `local_data/`; they are not committed. No personal student forms were used. Actual form accuracy should be measured later against an independently transcribed sample of the intended questionnaire scans.
