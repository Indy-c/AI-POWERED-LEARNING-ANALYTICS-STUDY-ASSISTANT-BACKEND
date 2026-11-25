import json
import re
import subprocess
import sys
from collections import Counter
from heapq import nsmallest
from pathlib import Path
from statistics import median
from threading import BoundedSemaphore


class PDFExtractionError(Exception):
    """The stored bytes could not be read within the PDF preparation limits."""


class PDFExtractionBusy(Exception):
    """All local PDF preparation slots are occupied."""


_pdf_slots = BoundedSemaphore(2)
_MAX_TEXT_CHARS = 120_000
_TIMEOUT_SECONDS = 20
_STUDY_MAX_PAGES = 300
_STUDY_MAX_TEXT_CHARS = 1_000_000
_STUDY_SECTION_PAGES = 8
_PAGE_COUNTER_SUFFIX = re.compile(r"\s+(?:[|:-]\s*)?page\s+\d+(?:\s+of\s+\d+)?$")

# Extract plain text from a PDF file
def extract_pdf_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError("PDF file was not found")
    
    return extract_pdf_text_from_bytes(path.read_bytes())

# Extract plain text from PDF bytes
def extract_pdf_text_from_bytes(file_bytes: bytes) -> str:
    return _run_pdf_worker(file_bytes).decode("utf-8")


def index_pdf_for_study(file_bytes: bytes) -> dict:
    """Extract numbered pages and inclusive section ranges for guided study."""
    output = _run_pdf_worker(file_bytes, "--study-index")
    try:
        return json.loads(output)
    except ValueError as exc:
        raise PDFExtractionError("Could not read PDF study index") from exc


def _run_pdf_worker(file_bytes: bytes, *args: str) -> bytes:
    if not _pdf_slots.acquire(blocking=False):
        raise PDFExtractionBusy("PDF preparation is busy")

    try:
        # MuPDF runs in a separate process so a slow file can be interrupted.
        result = subprocess.run(
            [sys.executable, __file__, *args],
            input=file_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=_TIMEOUT_SECONDS,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except subprocess.TimeoutExpired as exc:
        raise PDFExtractionError("PDF preparation timed out") from exc
    finally:
        _pdf_slots.release()

    if result.returncode != 0:
        raise PDFExtractionError("Could not read PDF text")
    return result.stdout


def _extract_in_worker(file_bytes: bytes) -> str:
    import fitz

    parts = []
    remaining = _MAX_TEXT_CHARS
    with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
        if not pdf.is_pdf or pdf.needs_pass:
            raise PDFExtractionError("Expected an unlocked PDF")
        for page in pdf:
            text = page.get_text().replace("\x00", "").strip()
            if text:
                parts.append(text[:remaining])
                remaining -= len(parts[-1]) + 1
            if remaining <= 0:
                break
    return "\n".join(parts).strip()


def _index_in_worker(file_bytes: bytes) -> dict:
    import fitz

    with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
        if not pdf.is_pdf or pdf.needs_pass or pdf.metadata.get("encryption"):
            raise PDFExtractionError("Expected an unlocked PDF")

        page_count = pdf.page_count
        index = {
            "status": "unsupported",
            "reason": None,
            "page_count": page_count,
            "unreadable_pages": [],
            "pages": [],
            "sections": [],
        }
        if page_count > _STUDY_MAX_PAGES:
            index["reason"] = "PDF exceeds the 300-page study limit"
            return index

        starts = _bookmark_starts(pdf, page_count) if page_count > _STUDY_SECTION_PAGES else []
        detect_headings = page_count > _STUDY_SECTION_PAGES and not starts
        page_headings = {}
        pages = []
        unreadable = []
        total_chars = 0
        for number, page in enumerate(pdf, start=1):
            text_page = page.get_textpage(flags=fitz.TEXTFLAGS_TEXT)
            text = text_page.extractText().replace("\x00", "").strip()
            total_chars += len(text)
            if total_chars > _STUDY_MAX_TEXT_CHARS:
                index["reason"] = "PDF exceeds the 1,000,000-character study limit"
                return index
            pages.append({"page": number, "text": text})
            if not text:
                unreadable.append(number)
            elif detect_headings:
                page_headings[number] = _page_heading_candidates(text_page)

        if detect_headings:
            starts = _heading_starts(page_headings)
        index.update(
            status="ready" if total_chars else "no_text",
            reason=None if total_chars else "PDF has no selectable text",
            unreadable_pages=unreadable,
            pages=pages,
            sections=_study_sections(page_count, starts, pages),
        )
        return index


def _bookmark_starts(pdf, page_count: int) -> list[tuple[int, str]]:
    try:
        bookmarks = pdf.get_toc()
    except (RuntimeError, ValueError):
        return []

    starts = {}
    for level, title, page in bookmarks:
        if level == 1 and 1 <= page <= page_count:
            title = " ".join(title.split())[:160].strip()
            if title:
                starts.setdefault(page, title)
    return sorted(starts.items())


def _page_heading_candidates(text_page) -> list[tuple[str, bool]]:
    layout = text_page.extractDICT()
    # Check only the leading lines, with a few more lines for a local body size.
    # The text page was built without images and is reused rather than reparsed.
    lines = nsmallest(
        10,
        (line for block in layout["blocks"] for line in block["lines"]
         if line["bbox"][1] < layout["height"] * 0.85),
        key=lambda line: (line["bbox"][1], line["bbox"][0]),
    )
    samples = []
    for line in lines:
        spans = [span for span in line["spans"] if span["text"].strip()]
        if not spans:
            continue
        title = " ".join("".join(span["text"] for span in spans).split())
        size = max(spans, key=lambda span: len(span["text"]))["size"]
        _, top, _, bottom = line["bbox"]
        samples.append((title, size, top, bottom))

    candidates = []
    for offset, (title, size, top, bottom) in enumerate(samples[:3]):
        if top > layout["height"] / 3 or not 4 <= len(title) <= 120:
            continue
        if not any(char.isalpha() for char in title):
            continue
        below = [other_size for _, other_size, other_top, _ in samples[offset + 1:]
                 if other_top >= bottom]
        body_size = median(below) if below else size
        candidates.append((title, size >= max(body_size * 1.3, body_size + 3)))
    return candidates


def _heading_starts(page_headings: dict[int, list[tuple[str, bool]]]) -> list[tuple[int, str]]:
    def heading_key(title):
        return _PAGE_COUNTER_SUFFIX.sub("", title.casefold())

    occurrences = Counter()
    for candidates in page_headings.values():
        occurrences.update({heading_key(title) for title, _ in candidates})

    starts = []
    for page, candidates in page_headings.items():
        for title, prominent in candidates:
            if prominent and occurrences[heading_key(title)] == 1:
                starts.append((page, title))
                break
    # One display title by itself is not enough evidence of section structure.
    return starts if len(starts) >= 2 else []


def _study_sections(page_count: int, starts: list[tuple[int, str]], pages: list[dict]) -> list[dict]:
    if starts:
        if starts[0][0] > 1:
            starts = [(1, "Front matter"), *starts]
        next_pages = [page for page, _ in starts[1:]] + [page_count + 1]
        sections = []
        for (start, title), next_page in zip(starts, next_pages):
            ranges = []
            chunk_start, chars = start, 0
            for page in pages[start - 1 : next_page - 1]:
                number, size = page["page"], len(page["text"])
                if number > chunk_start and (number - chunk_start >= 24 or chars + size > 56_000):
                    ranges.append((chunk_start, number - 1))
                    chunk_start, chars = number, 0
                chars += size
            ranges.append((chunk_start, next_page - 1))
            for number, (first, last) in enumerate(ranges, start=1):
                suffix = f" (part {number})" if len(ranges) > 1 else ""
                sections.append({
                    "title": title[:160 - len(suffix)].rstrip() + suffix, "start_page": first, "end_page": last,
                })
        return sections

    sections = []
    for start in range(1, page_count + 1, _STUDY_SECTION_PAGES):
        end = min(start + _STUDY_SECTION_PAGES - 1, page_count)
        title = "Whole document" if page_count <= _STUDY_SECTION_PAGES else f"Pages {start}-{end}"
        sections.append({"title": title, "start_page": start, "end_page": end})
    return sections


if __name__ == "__main__":
    try:
        file_bytes = sys.stdin.buffer.read()
        if sys.argv[1:] == ["--study-index"]:
            output = json.dumps(_index_in_worker(file_bytes), ensure_ascii=False)
        else:
            output = _extract_in_worker(file_bytes)
        sys.stdout.buffer.write(output.encode("utf-8"))
    except (PDFExtractionError, RuntimeError, ValueError):
        sys.exit(1)
