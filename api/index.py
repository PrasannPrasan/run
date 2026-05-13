import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

if os.environ.get("VERCEL"):
    os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/lead-enrichment.db")
    os.environ.setdefault("FRONTEND_URL", "/")

from app.main import app  # noqa: E402

