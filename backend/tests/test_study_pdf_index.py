import subprocess

import fitz
import pytest

from app.domains.documents import pdf_text


def _pdf(contents, *, bookmarks=(), password=None):
    with fitz.open() as pdf:
        for content in contents:
            page = pdf.new_page()
            if isinstance(content, str):
                if content:
                    page.insert_text((72, 72), content)
            else:
                for y, size, line in content:
                    page.insert_text((72, y), line, fontsize=size)
        if bookmarks:
            pdf.set_toc(bookmarks)
        if password is not None:
            return pdf.tobytes(
                encryption=fitz.PDF_ENCRYPT_AES_128,
                owner_pw="owner-password",
                user_pw=password,
            )
        return pdf.tobytes()


def _ranges(index):
    return [(section["start_page"], section["end_page"]) for section in index["sections"]]


def test_bookmarks_fit_the_persisted_title_limit():
    index = pdf_text.index_pdf_for_study(_pdf(["Notes"] * 10, bookmarks=[[1, "A" * 170, 1]]))
    assert _ranges(index) == [(1, 10)]
    assert len(index["sections"][0]["title"]) == 160


def test_large_bookmark_is_divided_into_manageable_ranges():
    index = pdf_text.index_pdf_for_study(_pdf(["Notes"] * 65, bookmarks=[[1, "Long chapter", 1]]))
    assert _ranges(index) == [(1, 24), (25, 48), (49, 65)]
    assert all(section["title"].startswith("Long chapter") for section in index["sections"])


def test_short_pdf_keeps_every_page_in_one_section():
    content = _pdf(["First page", "", "Last page"], bookmarks=[[1, "Last", 3]])

    index = pdf_text.index_pdf_for_study(content)

    assert set(index) == {"status", "reason", "page_count", "unreadable_pages", "pages", "sections"}
    assert index["status"] == "ready"
    assert index["reason"] is None
    assert index["page_count"] == 3
    assert index["unreadable_pages"] == [2]
    assert index["pages"] == [
        {"page": 1, "text": "First page"},
        {"page": 2, "text": ""},
        {"page": 3, "text": "Last page"},
    ]
    assert _ranges(index) == [(1, 3)]
    assert index["sections"][0]["title"]


def test_all_empty_pdf_preserves_page_numbers_and_reports_no_text():
    index = pdf_text.index_pdf_for_study(_pdf(["", " "]))

    assert index["status"] == "no_text"
    assert index["reason"]
    assert index["page_count"] == 2
    assert index["unreadable_pages"] == [1, 2]
    assert index["pages"] == [{"page": 1, "text": ""}, {"page": 2, "text": ""}]
    assert _ranges(index) == [(1, 2)]


def test_top_level_bookmarks_take_precedence_and_cover_front_matter():
    content = _pdf(
        [_slide(number) for number in range(1, 14)],
        bookmarks=[
            [1, "External reference", -1, {"kind": fitz.LINK_URI, "uri": "https://example.com"}],
            [1, "First chapter", 3],
            [2, "Nested topic", 4],
            [1, "Duplicate destination", 3],
            [1, "Second chapter", 9],
        ],
    )

    index = pdf_text.index_pdf_for_study(content)

    assert _ranges(index) == [(1, 2), (3, 8), (9, 13)]
    assert [section["title"] for section in index["sections"]] == [
        "Front matter", "First chapter", "Second chapter",
    ]


def _slide(number):
    return [
        (130, 24, f"Topic {number}"),
        (230, 12, "Discussion and examples"),
        (260, 12, "An exercise to work through"),
        (55, 29, f"Course notes | Page {number}"),
    ]


def test_prominent_slide_headings_ignore_running_headers_and_include_front_matter():
    content = _pdf(["Syllabus"] + [_slide(number) for number in range(2, 11)])

    index = pdf_text.index_pdf_for_study(content)

    assert _ranges(index) == [(number, number) for number in range(1, 11)]
    assert [section["title"] for section in index["sections"]] == [
        "Front matter", *(f"Topic {i}" for i in range(2, 11)),
    ]


@pytest.mark.parametrize("running_header", [False, True], ids=["plain-text", "repeated-header"])
def test_long_unstructured_pdf_uses_inclusive_eight_page_blocks(running_header):
    content = _pdf([
        [(40, 24, "Course notes"), (90, 12, f"Paragraph {number}")]
        if running_header else f"Paragraph {number}"
        for number in range(1, 18)
    ])

    index = pdf_text.index_pdf_for_study(content)

    assert index["status"] == "ready"
    assert _ranges(index) == [(1, 8), (9, 16), (17, 17)]
    assert [page["page"] for page in index["pages"]] == list(range(1, 18))


def test_pdf_over_page_limit_is_unsupported():
    index = pdf_text.index_pdf_for_study(_pdf([""] * 301))

    assert index["status"] == "unsupported"
    assert "300" in index["reason"]
    assert index["page_count"] == 301
    assert index["unreadable_pages"] == index["pages"] == index["sections"] == []


def _dense_page(last_line="a"):
    return [(20, 5, ("a" * 100 + "\n") * 99 + last_line)]


@pytest.mark.parametrize("extra", ["", "a"], ids=["at-limit", "over-limit"])
def test_study_text_cap_does_not_return_partial_indexes(extra):
    content = _pdf([_dense_page()] * 99 + [_dense_page("a" + extra)])

    index = pdf_text.index_pdf_for_study(content)

    assert index["page_count"] == 100
    if extra:
        assert index["status"] == "unsupported"
        assert "1,000,000" in index["reason"]
        assert index["unreadable_pages"] == index["pages"] == index["sections"] == []
    else:
        assert index["status"] == "ready"
        assert sum(len(page["text"]) for page in index["pages"]) == 1_000_000


def test_study_keeps_text_beyond_legacy_cap():
    content = _pdf([_dense_page()] * 13 + ["Text after the legacy cap"])

    legacy = pdf_text.extract_pdf_text_from_bytes(content)
    index = pdf_text.index_pdf_for_study(content)

    assert len(legacy) == 120_000
    assert "Text after the legacy cap" not in legacy
    assert index["status"] == "ready"
    assert index["pages"][-1] == {"page": 14, "text": "Text after the legacy cap"}


@pytest.mark.parametrize("password", ["locked", ""], ids=["password-required", "empty-user-password"])
def test_encrypted_pdf_raises_existing_extraction_error(password):
    with pytest.raises(pdf_text.PDFExtractionError):
        pdf_text.index_pdf_for_study(_pdf(["Private"], password=password))


def test_invalid_pdf_raises_existing_extraction_error():
    with pytest.raises(pdf_text.PDFExtractionError):
        pdf_text.index_pdf_for_study(b"Invalid PDF")


def test_study_shares_legacy_worker_slots():
    slots = pdf_text._pdf_slots
    with slots, slots:
        with pytest.raises(pdf_text.PDFExtractionBusy):
            pdf_text.index_pdf_for_study(b"")
        with pytest.raises(pdf_text.PDFExtractionBusy):
            pdf_text.extract_pdf_text_from_bytes(b"")


def test_study_times_out_at_twenty_seconds_and_releases_slot(monkeypatch):
    def time_out(args, **kwargs):
        assert kwargs["timeout"] == 20
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])

    monkeypatch.setattr(pdf_text.subprocess, "run", time_out)
    with pytest.raises(pdf_text.PDFExtractionError, match="timed out"):
        pdf_text.index_pdf_for_study(b"")

    slots = pdf_text._pdf_slots
    with slots:
        assert slots.acquire(blocking=False)
        slots.release()
