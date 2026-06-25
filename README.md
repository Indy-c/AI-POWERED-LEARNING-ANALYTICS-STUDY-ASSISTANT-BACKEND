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
- Supabase Postgres
- Supabase Storage
- Gemini AI API
- LangChain
- Docker
- Render
- GitHub Actions

## Local Development

Create local environment files from the examples:

```bash
copy .env.example .env
copy backend\.env.example backend\.env
```

Local Docker uses:

- FastAPI backend container
- local PostgreSQL container
- Supabase Storage bucket, usually `documents-dev`

Start the backend and local PostgreSQL:

```bash
docker compose up --build
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

Health check:

```text
http://127.0.0.1:8000/healthz
```

AI features use a basic fallback unless `GEMINI_API_KEY` is set.

Environment files:

- `.env` is used by Docker Compose from the project root.
- `backend/.env` is used when running backend commands directly from the `backend` folder.
- Real `.env` files are private and must not be committed.

Run database migrations from the backend folder:

```bash
cd backend
python -m alembic upgrade head
```

## Deployment

Current deployment shape:

- Render Web Service deploys the FastAPI backend from the `development` branch.
- Supabase Postgres stores application data.
- Supabase Storage stores uploaded PDF files.

Required Render environment variables:

```env
DATABASE_URL=postgresql+psycopg://...
JWT_SECRET_KEY=change-this-to-a-long-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_STORAGE_BUCKET=documents
GEMINI_API_KEY=
```

Deployed API documentation:

```text
https://studypilot-mamn.onrender.com/docs
```

Deployed health check:

```text
https://studypilot-mamn.onrender.com/healthz
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

Completed backend features:

- FastAPI project structure
- Docker and PostgreSQL setup
- Render deployment
- Supabase Postgres integration
- Supabase Storage integration
- JWT registration and login
- Protected user profile route
- PDF upload and document management
- Document delete endpoint
- PDF text extraction with PyMuPDF
- Alembic database migrations
- Basic AI summary, flashcard, and quiz generation endpoints
- Saved flashcards and flashcard delete endpoint
- Saved quiz attempts and scoring
- Analytics dashboard endpoint
- Basic and Gemini-ready study roadmap endpoint
- CORS middleware for local frontend integration
- Rate limiting for selected endpoints
- GitHub Actions backend test workflow

Possible next backend features:

- Add deployed frontend URL to CORS when frontend is deployed
- Real Gemini-powered flashcards and quizzes with stronger JSON handling
- Weak topic detection
- Signed private PDF download URLs
- More API integration tests
