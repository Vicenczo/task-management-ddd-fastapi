"""
Gunicorn configuration for production.

Worker model:
  - UvicornWorker: async ASGI worker, handles concurrent requests efficiently.
  - Workers: 2 * CPU_COUNT + 1 is the standard formula for I/O-bound apps.
  - Threads: 1 per worker (async handles concurrency, not threads).

Timeouts:
  - timeout: 30s — worker killed if silent for 30s (prevents zombie workers).
  - keepalive: 5s — how long to wait for next request on a keep-alive connection.
  - graceful_timeout: 30s — time for workers to finish current request on shutdown.

Logging:
  - accesslog: "-" means stdout (captured by Docker/Kubernetes log driver).
  - errorlog: "-" means stderr.
  - loglevel: "info" in production; set to "debug" via env var for troubleshooting.
"""
import multiprocessing
import os

# ── Worker configuration ─────────────────────────────────────
worker_class = "uvicorn.workers.UvicornWorker"
workers = int(os.getenv("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
threads = 1

# ── Network ──────────────────────────────────────────────────
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"
backlog = 2048

# ── Timeouts ─────────────────────────────────────────────────
timeout = 30
keepalive = 5
graceful_timeout = 30

# ── Logging ──────────────────────────────────────────────────
accesslog = "-"     # stdout
errorlog = "-"      # stderr
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sμs'

# ── Process naming ────────────────────────────────────────────
proc_name = "taskapi"