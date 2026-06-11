# AI-Powered Learning Analytics & Personalized Study Assistant Backend

Backend API for an AI-powered learning platform that supports PDF study material processing, AI-generated learning resources, quizzes, flashcards, analytics, and personalized study recommendations.

## Tech Stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- JWT Authentication
- bcrypt Password Hashing
- SlowAPI Rate Limiting
- PyMuPDF
- Gemini AI API
- LangChain
- Docker

## Local Development

Start the backend and PostgreSQL:

```bash
docker compose up --build
```

Run database migrations from the backend folder:

```bash
cd backend
python -m alembic upgrade head
```

API documentation:

```text
http://127.0.0.1:8000/docs
```
