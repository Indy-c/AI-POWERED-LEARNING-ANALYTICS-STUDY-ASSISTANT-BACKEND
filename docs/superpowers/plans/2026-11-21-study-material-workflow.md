# Study Material Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prepare PDFs on upload, restore generated materials on reload, and make recoverable errors actionable.

**Architecture:** The upload response includes the result of text extraction. PostgreSQL stores the latest summary, flashcard list, and roadmap on the owned document and keeps the existing quiz records for grading. The workspace rehydrates from a read-only API instead of generating on page load.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, PyMuPDF, React, Vite.

**Spec:** The accepted checklist in the StudyPilot project conversation.

## Steps

- [x] Add backend workflow tests for upload, older documents, restoration, and unsuccessful regeneration; confirm the tests fail against the old behavior.
- [x] Update document preparation and generation guards; retain the existing preview and missing-file behavior.
- [x] Add an additive migration and an owner-only endpoint for saved results. Restore existing quizzes without revealing their answer keys.
- [x] Update the workspace to restore saved material, prepare uploads automatically, and show actionable messages without clearing an earlier successful result.
- [x] Verify the migration and backend suite; lint, build, and exercise the frontend flow.
- [ ] Deploy the migration and backend before the frontend when ready.
