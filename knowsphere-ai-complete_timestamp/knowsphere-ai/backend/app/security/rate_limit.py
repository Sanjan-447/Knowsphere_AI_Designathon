"""
Rate limiting.

Redis-backed (shared with the response cache and Celery broker — no new
infrastructure needed) so limits are enforced correctly even across
multiple backend worker processes, not just per-process in memory.

Default limits are conservative starting points for a real deployment,
not tuned against production traffic this project has never seen — treat
them as a baseline to adjust once you have real usage data, not as
scientifically-derived thresholds.
"""
import os

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    default_limits=["200 per minute", "3000 per hour"],
    strategy="fixed-window",
)
