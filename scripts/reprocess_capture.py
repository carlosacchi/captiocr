"""
Standalone re-processor for raw capture files.

Reads a raw capture file (with timestamp blocks), runs the patched
ROVER + TF-IDF pipeline, and writes a *_processed.txt file with the
same metadata header format used by the live capture flow.

Usage:
    python scripts/reprocess_capture.py <raw_file.txt> [output_name]
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

# Make the captiocr package importable when running from the repo root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from captiocr.config.constants import APP_VERSION  # noqa: E402
from captiocr.core.text_processor import TextProcessor  # noqa: E402


TIMESTAMP_RE = re.compile(r'^\[\d{2}:\d{2}:\d{2}\]')
HEADER_KEYS = {
    'Caption capture started': 'capture_started',
    'Language': 'language',
    'Caption mode': 'caption_mode',
    'Version': 'source_version',
}


def parse_capture(filepath: Path) -> tuple[dict, list[tuple[str, str]]]:
    """Return (metadata, [(timestamp, text), ...]) extracted from a raw file."""
    metadata: dict = {}
    blocks: list[list[str]] = []
    current: list[str] = []

    with filepath.open('r', encoding='utf-8') as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                if current:
                    blocks.append(current)
                    current = []
                continue
            if TIMESTAMP_RE.match(stripped):
                if current:
                    blocks.append(current)
                current = [stripped]
                continue
            if current:
                current.append(stripped)
                continue
            # header line — try to parse "key: value"
            if ':' in stripped:
                key, _, value = stripped.partition(':')
                key = key.strip()
                if key in HEADER_KEYS:
                    metadata[HEADER_KEYS[key]] = value.strip()

    if current:
        blocks.append(current)

    text_blocks: list[tuple[str, str]] = []
    for block in blocks:
        if not block:
            continue
        ts_match = TIMESTAMP_RE.match(block[0])
        if not ts_match:
            continue
        ts = ts_match.group(0)
        body = ' '.join([block[0][len(ts):].strip(), *block[1:]]).strip()
        if body:
            text_blocks.append((ts, body))

    return metadata, text_blocks


def write_processed(out_path: Path, metadata: dict,
                    text_blocks: list[tuple[str, str]],
                    processed_blocks: list[tuple[str, str]],
                    stats: dict | None) -> None:
    with out_path.open('w', encoding='utf-8') as fh:
        fh.write("CaptiOCR Processed Transcription\n")
        fh.write(f"Version: {APP_VERSION}\n")
        if metadata.get('capture_started'):
            fh.write(f"Capture started: {metadata['capture_started']}\n")
        fh.write(f"Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        if metadata.get('language'):
            fh.write(f"Language: {metadata['language']}\n")
        fh.write(f"Original blocks: {len(text_blocks)}\n")
        fh.write(f"Processed blocks: {len(processed_blocks)}\n")

        if stats:
            fh.write("\n--- Processing Diagnostics ---\n")
            fh.write(f"Total frames: {stats['total_frames']}\n")
            fh.write(f"Chunks emitted: {stats['chunks_emitted']}\n")
            fh.write(f"Dropped (UI artifact): {stats['dropped_ui_artifact']}\n")
            fh.write(f"Dropped (OCR artifact): {stats['dropped_ocr_artifact']}\n")
            fh.write(f"Dropped (no novel words): {stats['dropped_empty_novel']}\n")
            fh.write(f"Dropped (low novelty score): {stats['dropped_low_score']}\n")
            fh.write(f"Merges performed: {stats['merges_performed']}\n")
            fh.write(f"Speaker names repaired: {stats.get('speaker_names_repaired', 0)}\n")
            fh.write(f"Possible drops detected: {stats['possible_drops_detected']}\n")

        fh.write(f"\n{'=' * 60}\n\n")
        for ts, text in processed_blocks:
            fh.write(f"{ts} {text}\n")


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: reprocess_capture.py <raw_file.txt> [output_basename]", file=sys.stderr)
        return 2

    raw_path = Path(sys.argv[1]).resolve()
    if not raw_path.exists():
        print(f"raw file not found: {raw_path}", file=sys.stderr)
        return 1

    output_basename = sys.argv[2] if len(sys.argv) > 2 else None

    metadata, text_blocks = parse_capture(raw_path)
    if not text_blocks:
        print("no timestamped blocks found", file=sys.stderr)
        return 1

    processor = TextProcessor()
    processed = processor.filter_duplicate_blocks_aggressive(text_blocks)
    stats = getattr(processor, '_last_post_process_stats', None)

    if output_basename:
        out_path = raw_path.parent / f"{output_basename}_processed.txt"
    else:
        out_path = raw_path.parent / f"{raw_path.stem}_processed.txt"

    write_processed(out_path, metadata, text_blocks, processed, stats)
    print(f"wrote: {out_path}")
    if stats:
        print(
            f"  frames: {stats['total_frames']} -> chunks: {stats['chunks_emitted']}, "
            f"speaker_repairs: {stats.get('speaker_names_repaired', 0)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
