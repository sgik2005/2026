# -*- coding: utf-8 -*-
"""cms-debate-kit 인용 검증기.

토론 로그에서 "근거 원문:" 뒤의 인용문을 추출해 발췌문과 대조한다.
완전 일치 -> V / 80% 이상 유사 -> 유사(다른 부분 표시) / 없음 -> X(환각 인용 경고)
표준 라이브러리만 사용. 사용법:
    python verify_quotes.py <발췌문.md> <토론로그.txt> <검증리포트.md>
"""
import sys
import io
import re
import difflib
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

MARK_OK, MARK_NEAR, MARK_MISS = "✔", "△", "✖"  # ✔ △ ✖
THRESHOLD = 0.8


def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().strip("\"'“”‘’")


def sentences(text: str):
    """발췌문을 문장 단위로 쪼갠다(대조 후보)."""
    body = re.sub(r"^#.*$", "", text, flags=re.M)
    parts = re.split(r"(?<=[.!?。])\s+|\n+", body)
    return [normalize(p) for p in parts if normalize(p)]


def extract_quotes(log_text: str):
    """로그에서 '근거 원문:' 뒤의 인용문을 줄 단위로 추출한다."""
    quotes = []
    for line in log_text.splitlines():
        m = re.search(r"근거\s*원문\s*[:：]\s*(.+)", line)
        if m:
            q = re.sub(r"[\(\[]\s*문단\s*\d+\s*[\)\]]\s*$", "", m.group(1).strip())
            q = normalize(q)
            if q:
                quotes.append(q)
    return quotes


def windows(text: str, size: int, step: int = 5):
    """원문을 인용 길이만큼의 창으로 잘라 대조 후보를 만든다."""
    for i in range(0, max(1, len(text) - size + 1), step):
        yield text[i : i + size]


def judge(quote: str, source_text: str, source_sents):
    flat = normalize(source_text)
    if quote in flat:
        return MARK_OK, 1.0, ""
    best, best_ratio = "", 0.0
    candidates = list(source_sents) + list(windows(flat, len(quote)))
    for s in candidates:
        r = difflib.SequenceMatcher(None, quote, s).ratio()
        if r > best_ratio:
            best, best_ratio = s, r
    if best_ratio >= THRESHOLD:
        diff = []
        sm = difflib.SequenceMatcher(None, quote, best)
        for op, a1, a2, b1, b2 in sm.get_opcodes():
            if op != "equal" and (quote[a1:a2].strip() or best[b1:b2].strip()):
                diff.append(f"인용 '{quote[a1:a2]}' ↔ 원문 '{best[b1:b2]}'")
        return MARK_NEAR, best_ratio, "; ".join(diff[:3]) or "공백·문장부호 차이"
    return MARK_MISS, best_ratio, best[:40]


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    src_path, log_path, out_path = map(Path, sys.argv[1:4])
    source_text = src_path.read_text(encoding="utf-8")
    log_text = log_path.read_text(encoding="utf-8")
    source_sents = sentences(source_text)
    quotes = extract_quotes(log_text)

    rows, counts = [], {MARK_OK: 0, MARK_NEAR: 0, MARK_MISS: 0}
    for i, q in enumerate(quotes, 1):
        mark, ratio, note = judge(q, source_text, source_sents)
        counts[mark] += 1
        if mark == MARK_MISS:
            note = f"발췌문에 없음 (최근접: {note}...)" if note else "발췌문에 없음"
        rows.append(f"| {i} | {q[:60]} | {mark} | {ratio:.0%} | {note} |")

    lines = [
        "# 인용 검증리포트",
        "",
        f"- 발췌문: `{src_path.name}` / 토론 로그: `{log_path.name}`",
        f"- 인용 {len(quotes)}건 — {MARK_OK} 일치 {counts[MARK_OK]} / "
        f"{MARK_NEAR} 유사 {counts[MARK_NEAR]} / {MARK_MISS} 없음 {counts[MARK_MISS]}",
        "",
        "| # | 인용문 | 판정 | 유사도 | 비고 |",
        "|---|--------|------|--------|------|",
        *rows,
    ]
    if counts[MARK_MISS]:
        lines += ["", f"> {MARK_MISS} 판정은 환각 인용일 수 있습니다. 해당 인용을 발췌문에서 직접 검색해 확인하세요."]
    if not quotes:
        lines += ["", "> 로그에서 '근거 원문:' 표기를 찾지 못했습니다. 토론 로그에 표기가 유지됐는지 확인하세요."]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"검증 완료: {len(quotes)}건 -> {out_path}")


if __name__ == "__main__":
    main()
