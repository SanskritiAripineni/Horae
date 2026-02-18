"""Build one CSV containing by_type, intro_concl, and raw extracted text."""

from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

import fitz
import pandas as pd

from _bootstrap import bootstrap_local_src

bootstrap_local_src()

from mindful_rag.config import INDEX_CSV, PDF_DIR
from mindful_rag.ingest_by_type import extract_text_by_type, find_pdf_match
from mindful_rag.ingest_intro_concl import extract_sections


def _pick_text(row: pd.Series, keys: list[str], default: str = "") -> str:
    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return default


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _extract_raw_full_text(pdf_path: Path) -> str:
    try:
        doc = fitz.open(str(pdf_path))
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return _clean_text(text)
    except Exception:
        return ""


def _default_output_path(input_csv: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return input_csv.parent / f"research_index_ingestions_{stamp}.csv"


def build_csv(input_csv: Path, output_csv: Path) -> None:
    df = pd.read_csv(input_csv)
    pdf_files = [p.name for p in Path(PDF_DIR).glob("*.pdf")]

    rows: list[dict[str, object]] = []
    missing_match = 0

    for idx, row in df.iterrows():
        title = _pick_text(row, ["paper_title", "title", "Paper Title"], default="Untitled")
        paper_type = _pick_text(row, ["paper_type", "Paper Type"], default="Unknown")
        matched_filename, match_score, match_method = find_pdf_match(title, pdf_files)

        by_type_text = ""
        intro_concl_text = ""
        raw_text = ""

        if matched_filename:
            pdf_path = Path(PDF_DIR) / matched_filename
            raw_text = _extract_raw_full_text(pdf_path)
            if raw_text:
                by_type_text = _clean_text(extract_text_by_type(raw_text, paper_type))
            intro_concl_text, _, _ = extract_sections(str(pdf_path))
            intro_concl_text = _clean_text(intro_concl_text)
        else:
            missing_match += 1

        rows.append(
            {
                "id": _pick_text(row, ["id", "ID"], default=str(idx + 1)),
                "paper_title": title,
                "cluster": _pick_text(row, ["cluster", "Cluster"]),
                "category": _pick_text(row, ["category", "Category (The Folder)"]),
                "paper_type": paper_type,
                "main_mechanism": _pick_text(row, ["main_mechanism", "Main Mechanism (Tags)"]),
                "filename_link": _pick_text(row, ["filename_link", "Filename/Link"]),
                "match_score": int(match_score),
                "match_method": match_method,
                "matched_pdf": matched_filename or "",
                "by_type_text": by_type_text,
                "intro_concl_text": intro_concl_text,
                "raw_text": raw_text,
                "by_type_chars": len(by_type_text),
                "intro_concl_chars": len(intro_concl_text),
                "raw_chars": len(raw_text),
            }
        )

    out_df = pd.DataFrame(rows)
    out_df.to_csv(output_csv, index=False)

    print(f"output_csv={output_csv}")
    print(f"rows={len(out_df)}")
    print(f"missing_match={missing_match}")
    print(f"by_type_nonempty={(out_df['by_type_text'].str.len() > 0).sum()}")
    print(f"intro_concl_nonempty={(out_df['intro_concl_text'].str.len() > 0).sum()}")
    print(f"raw_nonempty={(out_df['raw_text'].str.len() > 0).sum()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build combined extraction CSV (by_type + intro_concl + raw).")
    parser.add_argument(
        "--input-csv",
        default=str(INDEX_CSV),
        help="Input index CSV path.",
    )
    parser.add_argument(
        "--output-csv",
        default="",
        help="Output CSV path. If omitted, writes timestamped file in data/index/.",
    )
    args = parser.parse_args()

    input_csv = Path(args.input_csv).expanduser().resolve()
    output_csv = (
        Path(args.output_csv).expanduser().resolve()
        if str(args.output_csv).strip()
        else _default_output_path(input_csv)
    )

    build_csv(input_csv=input_csv, output_csv=output_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
