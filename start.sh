#!/bin/bash
export DATABASE_URL="sqlite+aiosqlite:///./newshub.db"
export SECRET_KEY="dev-secret-key-for-kursovaya-2024"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload