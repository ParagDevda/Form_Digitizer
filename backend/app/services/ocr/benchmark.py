"""Ground-truth CER/WER helpers. Scores are only produced from supplied labels."""

import re


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, ref_token in enumerate(reference, 1):
        current = [row]
        for column, hyp_token in enumerate(hypothesis, 1):
            current.append(min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (ref_token != hyp_token)))
        previous = current
    return previous[-1]


def error_rates(reference: str, hypothesis: str) -> tuple[float, float]:
    ref_chars = list(reference)
    hyp_chars = list(hypothesis)
    ref_words = re.findall(r"\b[\w']+\b", reference.casefold())
    hyp_words = re.findall(r"\b[\w']+\b", hypothesis.casefold())
    cer = edit_distance(ref_chars, hyp_chars) / max(1, len(ref_chars))
    wer = edit_distance(ref_words, hyp_words) / max(1, len(ref_words))
    return cer, wer
