# -*- coding: utf-8 -*-
"""발췌문과 토론 로그의 직접 인용을 대조해 Markdown 리포트를 만든다.

사용법: python verify_quotes.py <발췌문.md> <토론로그.txt> <검증리포트.md>
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

MARK_OK, MARK_NEAR, MARK_MISS = "✔", "△", "✖"
THRESHOLD = 0.8
CITATION_AT_END = re.compile(
    r"\s*(?:\(\s*(?:문단\s*)?\[?\d+\]?\s*\)|\[\s*(?:문단\s*)?\d+\s*\])\s*$"
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().strip("\"'“”‘’")


def markdown_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def source_sentences(text: str) -> list[str]:
    body = re.sub(r"^#.*$", "", text, flags=re.MULTILINE)
    parts = re.split(r"(?<=[.!?。])\s+|\n+", body)
    return [normalize(part) for part in parts if normalize(part)]


def extract_quotes(log_text: str) -> list[str]:
    quotes = []
    for line in log_text.splitlines():
        match = re.search(r"근거\s*원문\s*[:：]\s*(.+)", line)
        if match:
            quote = normalize(CITATION_AT_END.sub("", match.group(1).strip()))
            if quote:
                quotes.append(quote)
    return quotes


def windows(text: str, size: int, step: int = 5):
    if len(text) <= size:
        yield text
        return
    for index in range(0, len(text) - size + 1, step):
        yield text[index:index + size]
    if (len(text) - size) % step:
        yield text[-size:]


def judge(quote: str, source_text: str, sentences: list[str]):
    flat = normalize(source_text)
    if quote in flat:
        return MARK_OK, 1.0, ""
    best, ratio = "", 0.0
    for candidate in [*sentences, *windows(flat, len(quote))]:
        candidate_ratio = difflib.SequenceMatcher(None, quote, candidate).ratio()
        if candidate_ratio > ratio:
            best, ratio = candidate, candidate_ratio
    if ratio >= THRESHOLD:
        differences = []
        for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, quote, best).get_opcodes():
            if op != "equal" and (quote[a1:a2].strip() or best[b1:b2].strip()):
                differences.append(f"인용 '{quote[a1:a2]}' ↔ 원문 '{best[b1:b2]}'")
        return MARK_NEAR, ratio, "; ".join(differences[:3]) or "공백·문장부호 차이"
    return MARK_MISS, ratio, best[:60]


def build_report(source_path: Path, log_path: Path) -> str:
    source_text = source_path.read_text(encoding="utf-8")
    quotes = extract_quotes(log_path.read_text(encoding="utf-8"))
    sentences = source_sentences(source_text)
    counts = {MARK_OK: 0, MARK_NEAR: 0, MARK_MISS: 0}
    rows = []
    for number, quote in enumerate(quotes, 1):
        mark, ratio, note = judge(quote, source_text, sentences)
        counts[mark] += 1
        if mark == MARK_MISS:
            note = f"발췌문에서 확인 불가 (최근접: {note}...)" if note else "발췌문에서 확인 불가"
        rows.append(
            f"| {number} | {markdown_escape(quote[:80])} | {mark} | {ratio:.0%} | {markdown_escape(note)} |"
        )
    lines = [
        "# 인용 검증리포트", "",
        f"- 발췌문: `{source_path.name}` / 토론 로그: `{log_path.name}`",
        f"- 인용 {len(quotes)}건 — {MARK_OK} 일치 {counts[MARK_OK]} / {MARK_NEAR} 유사 {counts[MARK_NEAR]} / {MARK_MISS} 없음 {counts[MARK_MISS]}",
        "", "| # | 인용문 | 판정 | 유사도 | 비고 |", "|---|---|---|---|---|", *rows,
    ]
    if counts[MARK_MISS]:
        lines.extend(["", f"> {MARK_MISS} 판정은 발췌문에서 확인 불가한 인용입니다. 발췌문을 직접 대조하세요."])
    if not quotes:
        lines.extend(["", "> 로그에서 `근거 원문:` 표기를 찾지 못했습니다. 로그 형식을 확인하세요."])
    return "\n".join(lines) + "\n"


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 1
    source_path, log_path, output_path = map(Path, sys.argv[1:4])
    if not source_path.is_file() or not log_path.is_file():
        print("입력 파일을 찾을 수 없습니다.", file=sys.stderr)
        return 2
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_report(source_path, log_path), encoding="utf-8")
    print(f"검증 완료: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
