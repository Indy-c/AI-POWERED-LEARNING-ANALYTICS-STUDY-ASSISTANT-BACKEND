from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.domains.documents import router as documents_router
from app.domains.documents.model import Document


def test_read_document_text_returns_409_for_missing_pdf(monkeypatch):
    def missing_pdf(_document):
        raise FileNotFoundError("PDF file was not found")

    app = FastAPI()
    app.include_router(documents_router.router)
    app.dependency_overrides[documents_router.get_db] = lambda: None
    app.dependency_overrides[documents_router.get_current_user] = lambda: None

    monkeypatch.setattr(
        documents_router, "get_user_document", lambda *_: Document(id=7)
    )
    monkeypatch.setattr(documents_router, "download_document_bytes", missing_pdf)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/documents/7/text")

    assert response.status_code == 409