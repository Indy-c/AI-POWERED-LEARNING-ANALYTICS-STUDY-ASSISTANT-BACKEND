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
- Pytest
- PyMuPDF
- Gemini AI API
- LangChain
- Docker

## Local Development

Start the backend and PostgreSQL:

```bash
docker compose up --build
```

AI features use a basic fallback unless `GEMINI_API_KEY` is set in `backend/.env`.

Environment files:

- `.env.example` is for Docker Compose variables from the project root.
- `backend/.env.example` is for running the backend directly from the `backend` folder.

Run database migrations from the backend folder:

```bash
cd backend
python -m alembic upgrade head
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

## Testing

Run backend tests from the `backend` folder:

```bash
cd backend
python -m pytest -v
```

### Git Pre-Push Hook

This project includes a pre-push hook that runs backend tests before pushing.

Enable it once after cloning:

```bash
git config core.hooksPath .githooks
```

## Development Status

Completed backend foundations:

- FastAPI project structure
- Docker and PostgreSQL setup
- JWT registration and login
- Protected user profile route
- PDF upload and document management
- PDF text extraction with PyMuPDF
- Alembic database migrations
- Basic AI summary, flashcard, and quiz generation endpoints
- Rate limiting for authentication and AI endpoints

Planned backend features:

- Real Gemini-powered flashcards and quizzes
- Saved quiz attempts and scoring
- Weak topic detection
- Personalized study roadmap
- Analytics endpoints

```

```
