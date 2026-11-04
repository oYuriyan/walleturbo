from urllib.parse import parse_qs, urlparse
import httpx2
from authlib.integrations.starlette_client import OAuth
from app import main


def test_login_creates_pkce_state_and_nonce(client, monkeypatch):
    issuer = "https://identity.example"
    oauth = OAuth()
    oauth.register(
        "identity",
        client_id="test-client",
        client_secret="test-secret",
        server_metadata_url=issuer + "/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid profile",
            "code_challenge_method": "S256",
            "transport": httpx2.MockTransport(
                lambda request: httpx2.Response(
                    200,
                    json={
                        "issuer": issuer,
                        "authorization_endpoint": issuer + "/authorize",
                        "token_endpoint": issuer + "/token",
                        "jwks_uri": issuer + "/jwks",
                    },
                )
            ),
        },
    )
    monkeypatch.setattr(main.conf, "oidc_issuer", issuer)
    monkeypatch.setattr(main, "oauth", oauth)
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 302
    params = parse_qs(urlparse(response.headers["location"]).query)
    assert params["code_challenge_method"] == ["S256"]
    assert params["state"] and params["nonce"] and params["code_challenge"]
