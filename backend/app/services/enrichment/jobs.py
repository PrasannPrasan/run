from __future__ import annotations

import threading

from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from app.db.models import Lookup, LookupStatus
from app.db.session import SessionLocal
from app.services.enrichment.waterfall import WaterfallOrchestrator
from app.settings import settings


def run_lookup_job(lookup_id: int) -> None:
    db: Session = SessionLocal()
    try:
        lookup = db.query(Lookup).filter(Lookup.id == lookup_id).one_or_none()
        if not lookup:
            return
        try:
            WaterfallOrchestrator(db).run(lookup)
        except Exception as exc:
            lookup.status = LookupStatus.failed
            lookup.error_message = str(exc)
            db.add(lookup)
            db.commit()
    finally:
        db.close()


def run_lookup_job_in_thread(lookup_id: int) -> None:
    thread = threading.Thread(target=run_lookup_job, args=(lookup_id,), daemon=True)
    thread.start()


def enqueue_lookup(lookup_id: int) -> bool:
    try:
        redis_conn = Redis.from_url(settings.redis_url)
        q = Queue("enrichment", connection=redis_conn)
        q.enqueue("app.services.enrichment.jobs.run_lookup_job", lookup_id)
        return True
    except Exception:
        return False
