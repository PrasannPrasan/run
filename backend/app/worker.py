import os

from redis import Redis
from rq import Queue, SimpleWorker, Worker

from app.settings import settings


def main() -> None:
    redis_conn = Redis.from_url(settings.redis_url)
    q = Queue("enrichment", connection=redis_conn)
    # Windows has no os.fork(), so use SimpleWorker there.
    worker_cls = SimpleWorker if os.name == "nt" else Worker
    worker = worker_cls([q], connection=redis_conn)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()

