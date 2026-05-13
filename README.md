# Lead Enrichment Dashboard

FastAPI + React dashboard for enriching a LinkedIn profile URL with:

- Full name
- Current company
- Current designation
- Total years of experience
- Work history / experience timeline
- Email address(es)
- Phone number(s)
- Field-level confidence and source tracking
- Per-lookup provider cost tracking

## Researched Provider Strategy

The lowest-cost practical waterfall is:

1. **Cache first**: reuse a completed lookup for the same user and LinkedIn URL.
2. **Apify first** for profile basics and work history. Apify's Free plan includes **$5/month prepaid usage**, and the selected LinkedIn profile actor supports API usage without LinkedIn cookies.
3. **Lusha second** only when contacts are still missing and a Lusha API key is configured. Lusha's public pricing advertises up to **70 free credits/month**, but its API help notes API-key access may depend on plan. API credit examples currently show email reveal, phone reveal, and request/result credits.
4. **Apollo third** for email, company/title, employment-history fallback, and optional async phone enrichment. Apollo's docs say enrichment endpoints such as `v1/people/match` consume credits and the People Enrichment API accepts a LinkedIn URL.
5. **RocketReach last** as coverage insurance for missing contact data because lookup/API access is generally plan/credit based.

Proxycurl is excluded: Nubela's 2026 Proxycurl update says Proxycurl API is no longer available after the LinkedIn lawsuit and is now historical only.

Primary sources:

- Apify pricing: https://apify.com/pricing
- Apify LinkedIn profile actor: https://apify.com/anchor/linkedin-profile-enrichment
- Lusha pricing: https://www.lusha.com/pricing/
- Lusha API credit docs: https://info.lusha.com/en/articles/163856-all-there-is-to-know-about-lusha-s-api
- Apollo API pricing: https://docs.apollo.io/docs/api-pricing
- Apollo People Enrichment: https://docs.apollo.io/reference/people-enrichment
- Proxycurl status: https://nubela.co/blog/what-is-proxycurl-api-now-in-2026-im-the-founder/

## Architecture

Backend:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/enrich`
- `GET /api/enrich/lookups/{id}`
- `GET /api/enrich/lookups`
- `GET /api/enrich/strategy`
- `POST /api/webhooks/apollo-phone`
- Provider clients: Apify, Lusha, Apollo, RocketReach
- Waterfall orchestrator with provider locks, cache reuse, confidence scoring, cost snapshots, and sync fallback when Redis is unavailable

Frontend:

- Login/register
- LinkedIn URL one-click enrichment
- Provider waterfall and key-status panel
- Contact snapshot with confidence/source attribution
- Work history timeline
- Cost tracking and lookup history

## Quick Start

Start Redis:

```bash
docker compose up -d
```

Start the backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install -e .
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Start the worker in a second terminal:

```bash
cd backend
.venv\Scripts\activate
python -m app.worker
```

Start the frontend:

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Open http://localhost:5173.

If port `8000` is already in use, start the API with another port such as `8002` and set `frontend/.env` to `VITE_API_BASE_URL=http://127.0.0.1:8002` before running Vite.

## Provider Keys

Set these in `backend/.env`:

```env
APIFY_TOKEN=
APIFY_ACTOR_ID=anchor~linkedin-profile-enrichment
LUSHA_API_KEY=
APOLLO_API_KEY=
ROCKETREACH_API_KEY=
ROCKETREACH_BASE_URL=https://api.rocketreach.co/api/v2
PUBLIC_WEBHOOK_BASE_URL=
```

`PUBLIC_WEBHOOK_BASE_URL` is needed only for Apollo phone webhook callbacks. For local testing, expose `localhost:8000` with ngrok or Cloudflare Tunnel and set this value to the public HTTPS URL.

## Vercel Deploy

This repo includes a Vercel config for a single project:

- React frontend is built from `frontend/`.
- FastAPI is exposed as a Vercel Python function through `api/index.py`.
- Frontend requests use same-origin `/api/...` in production.

Set these Vercel environment variables:

```env
APP_ENV=production
JWT_SECRET=<long-random-secret>
DATABASE_URL=sqlite:////tmp/lead-enrichment.db
APIFY_TOKEN=<your-token>
APIFY_ACTOR_ID=scrapemint/linkedin-profile-scraper
APOLLO_API_KEY=<your-key>
ROCKETREACH_API_KEY=<your-key>
LUSHA_API_KEY=
ROCKETREACH_BASE_URL=https://api.rocketreach.co/api/v2
PUBLIC_WEBHOOK_BASE_URL=https://<your-vercel-domain>
```

Vercel serverless storage is ephemeral, so the SQLite database is suitable only for a demo deployment. For production, replace it with Postgres and use a durable queue/worker platform for long-running enrichment jobs.

## Notes

- I cannot create third-party accounts or obtain secret API keys for you. The app is wired to use your keys as soon as they are added to `backend/.env`.
- Keep provider keys server-side only.
- Store only fields you need, honor deletion/opt-out requests, and review each provider's terms before production use.
