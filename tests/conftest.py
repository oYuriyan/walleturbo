import os
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SESSION_SECRET"] = "segredo-de-testes-com-mais-de-32-caracteres"
os.environ["BASE_URL"] = "http://testserver"

import json
import time
import pytest
import fakeredis
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db import Base, db_session
from app import security, main


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine)
    def db():
        with sessions() as session:
            yield session
    redis = fakeredis.FakeRedis(decode_responses=True)
    # fakeredis sem extra Lua: implementação equivalente apenas para o contador de teste.
    def counter(script, count, key, ttl):
        n = redis.incr(key)
        if n == 1:
            redis.expire(key, int(ttl))
        return n
    monkeypatch.setattr(redis, "eval", counter)
    monkeypatch.setattr(security, "store", redis)
    monkeypatch.setattr(main, "store", redis)
    app.dependency_overrides[db_session] = db
    with TestClient(app) as client:
        client.redis = redis
        yield client
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def login(client):
    def authenticate(user="alice"):
        sid = ("a" if user == "alice" else "b") * 64
        client.redis.setex(security.session_key(sid), 1800, json.dumps({"user":user,"csrf":"test-csrf","created":time.time()}))
        client.cookies.clear()
        client.cookies.set(security.COOKIE, sid)
        client.headers.update({"Origin":"http://testserver","X-CSRF-Token":"test-csrf"})
    return authenticate
