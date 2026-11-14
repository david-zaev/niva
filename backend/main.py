"""Niva backend: FastAPI app. Skeleton with /health; routes from DESIGN.md get added here."""
import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Niva API", version="0.1.0")

# Comma-separated list in .env, e.g. "https://<org>.github.io,http://localhost:5173"
origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "niva-api", "time": datetime.now(timezone.utc).isoformat()}
