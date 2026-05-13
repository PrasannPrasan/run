## Backend (FastAPI)

### Prereqs
- Python 3.11+
- Docker (for Redis), optional but recommended

### Setup
```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -U pip
pip install -e .
copy .env.example .env
```

### Start Redis (recommended)
From repo root:
```bash
docker compose up -d
```

### Run API
```bash
cd backend
.venv\\Scripts\\activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run worker
```bash
cd backend
.venv\\Scripts\\activate
python -m app.worker
```
