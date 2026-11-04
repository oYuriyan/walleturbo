"""Gera sessão sintética de curta duração; saída deve ser canalizada ao teste, nunca logada."""

import hashlib
import json
import os
import secrets
import time
from redis import Redis

if os.environ.get("WALLETURBO_INTEGRATION") != "1":
    raise RuntimeError("Somente ambiente de testes")
sid = secrets.token_hex(32)
redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
redis.setex(
    "session:" + hashlib.sha256(sid.encode()).hexdigest(),
    180,
    json.dumps(
        {
            "user": "browser-synthetic-" + secrets.token_hex(16),
            "csrf": secrets.token_hex(32),
            "created": time.time(),
        }
    ),
)
print(json.dumps({"sid": sid}))
