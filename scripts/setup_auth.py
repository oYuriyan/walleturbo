"""Gera segredos exclusivos de desenvolvimento sem exibi-los."""

import os
from pathlib import Path
import secrets

path = Path(".env.auth")
values = {
    "KEYCLOAK_ADMIN_USER": "walleturbo-admin",
    "KEYCLOAK_ADMIN_PASSWORD": secrets.token_urlsafe(32),
    "KEYCLOAK_DB_PASSWORD": secrets.token_urlsafe(32),
    "WALLETURBO_OIDC_SECRET": secrets.token_urlsafe(32),
}
try:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit(
        ".env.auth já existe; preservado. Não gere novos segredos para volumes existentes."
    )
with os.fdopen(fd, "w") as stream:
    stream.write("".join(f"{key}={value}\n" for key, value in values.items()))
print(
    "Configuração local criada em .env.auth (permissão 0600). Consulte docs/KEYCLOAK.md."
)
