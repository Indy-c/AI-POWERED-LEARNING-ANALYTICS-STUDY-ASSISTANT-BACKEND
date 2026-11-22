from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domains.documents import router as documents_router
from app.domains.documents.model import Document
from app.domains.users.model import User


def test_read_document_text_returns_409_for_missing_pdf(monkeypatch):
    def missing_pdf(_document):
        raise FileNotFoundError("PDF file was not found")

    app = FastAPI()
    app.include_router(documents_router.router)
    app.dependency_overrides[documents_router.get_db] = lambda: None
    app.dependency_overrides[documents_router.get_current_user] = lambda: None

    monkeypatch.setattr(
        "app.domains.documents.dependencies.get_user_document", lambda *_: Document(id=7)
    )
    monkeypatch.setattr("app.domains.documents.service.download_document_bytes", missing_pdf)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/documents/7/text")

    assert response.status_code == 409


def test_open_original_pdf_returns_private_bytes_without_preparing_text(monkeypatch):
    app = FastAPI()
    app.include_router(documents_router.router)
    app.dependency_overrides[documents_router.get_db] = lambda: None
    app.dependency_overrides[documents_router.get_current_user] = lambda: User(id=3)
    document = Document(id=7, owner_id=3, original_filename="lecture notes.pdf", processing_status="no_text")
    pdf = b"%PDF-1.7\nOriginal bytes\n%%EOF"

    def find_owned_document(_db, document_id, user):
        assert document_id == 7 and user.id == 3
        return document

    monkeypatch.setattr("app.domains.documents.dependencies.get_user_document", find_owned_document)
    monkeypatch.setattr("app.domains.documents.dependencies.download_document_bytes", lambda _: pdf)

    with TestClient(app) as client:
        response = client.get("/documents/7/file")

    assert response.status_code == 200
    assert response.content == pdf
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"] == "inline; filename*=UTF-8''lecture%20notes.pdf"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_open_original_pdf_does_not_reach_storage_without_owner(monkeypatch):
    app = FastAPI()
    app.include_router(documents_router.router)
    app.dependency_overrides[documents_router.get_db] = lambda: None
    app.dependency_overrides[documents_router.get_current_user] = lambda: User(id=4)

    def unexpected_download(_document):
        raise AssertionError("Storage must not be called for someone else's PDF")

    monkeypatch.setattr("app.domains.documents.dependencies.get_user_document", lambda *_: None)
    monkeypatch.setattr("app.domains.documents.dependencies.download_document_bytes", unexpected_download)

    with TestClient(app) as client:
        response = client.get("/documents/7/file")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_open_original_pdf_requires_sign_in():
    app = FastAPI()
    app.include_router(documents_router.router)
    app.dependency_overrides[documents_router.get_db] = lambda: None

    with TestClient(app) as client:
        response = client.get("/documents/7/file")

    assert response.status_code in {401, 403}


def test_open_original_pdf_returns_409_when_the_file_is_missing(monkeypatch):
    app = FastAPI()
    app.include_router(documents_router.router)
    app.dependency_overrides[documents_router.get_db] = lambda: None
    app.dependency_overrides[documents_router.get_current_user] = lambda: User(id=3)

    def missing_pdf(_document):
        raise FileNotFoundError("PDF file was not found")

    monkeypatch.setattr("app.domains.documents.dependencies.get_user_document", lambda *_: Document(id=7))
    monkeypatch.setattr("app.domains.documents.dependencies.download_document_bytes", missing_pdf)

    with TestClient(app) as client:
        response = client.get("/documents/7/file")

    assert response.status_code == 409
    assert response.json() == {"detail": "Document file is missing. Please upload the PDF again."}
