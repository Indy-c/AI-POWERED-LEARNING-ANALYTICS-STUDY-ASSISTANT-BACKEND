import subprocess
import sys
from pathlib import Path
from threading import BoundedSemaphore


class PDFExtractionError(Exception):
    """The stored bytes could not be read within the PDF preparation limits."""


class PDFExtractionBusy(Exception):
    """All local PDF preparation slots are occupied."""


_pdf_slots = BoundedSemaphore(2)
_MAX_TEXT_CHARS = 120_000
_TIMEOUT_SECONDS = 20

# Extract plain text from a PDF file
def extract_pdf_text(file_path: str) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError("PDF file was not found")
    
    return extract_pdf_text_from_bytes(path.read_bytes())

# Extract plain text from PDF bytes
def extract_pdf_text_from_bytes(file_bytes: bytes) -> str:
    if not _pdf_slots.acquire(blocking=False):
        raise PDFExtractionBusy("PDF preparation is busy")

    try:
        # MuPDF runs in a separate process so a slow file can be interrupted.
        result = subprocess.run(
            [sys.executable, __file__],
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
    return result.stdout.decode("utf-8")


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


if __name__ == "__main__":
    try:
        sys.stdout.buffer.write(_extract_in_worker(sys.stdin.buffer.read()).encode("utf-8"))
    except (PDFExtractionError, RuntimeError, ValueError):
        sys.exit(1)
