"""Usuário sintético para CI isolado; sem criar sessão na aplicação."""

import json
import os
import secrets
import uuid
import httpx2

if os.environ.get("WALLETURBO_INTEGRATION") != "1":
    raise SystemExit("Execução restrita ao ambiente de integração.")
base = "http://auth.walleturbo.localhost:8080"
with httpx2.Client(timeout=15, trust_env=False) as client:
    response = client.post(
        base + "/realms/master/protocol/openid-connect/token",
        data={
            "client_id": "admin-cli",
            "grant_type": "password",
            "username": os.environ["KEYCLOAK_ADMIN_USER"],
            "password": os.environ["KEYCLOAK_ADMIN_PASSWORD"],
        },
    )
    response.raise_for_status()
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    username = "ci-" + uuid.uuid4().hex
    password = "Ci-9aA-" + secrets.token_urlsafe(24)
    response = client.post(
        base + "/admin/realms/walleturbo/users",
        json={
            "username": username,
            "enabled": True,
            "emailVerified": True,
            "firstName": "Pessoa",
            "lastName": "Sintética",
            "email": username + "@example.invalid",
            "requiredActions": ["CONFIGURE_TOTP"],
            "credentials": [
                {"type": "password", "value": password, "temporary": False}
            ],
        },
    )
    response.raise_for_status()
    print(json.dumps({"username": username, "password": password}))
