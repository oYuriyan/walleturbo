"""Compatibilidade do transporte OAuth; não homologa um provedor OIDC real."""

import asyncio
from urllib.parse import parse_qs

import httpx2
import pytest
from authlib.integrations.httpx_client import AsyncOAuth2Client, OAuthError


@pytest.mark.parametrize("accepted", [True, False])
def test_authorization_code_transport_preserves_pkce_and_rejects_errors(accepted):
    verifier = "v" * 64

    def token_endpoint(request):
        assert request.method == "POST"
        assert str(request.url) == "https://issuer.example/token"
        form = parse_qs(request.content.decode())
        assert form["grant_type"] == ["authorization_code"]
        assert form["code"] == ["synthetic-code"]
        assert form["code_verifier"] == [verifier]
        assert form["redirect_uri"] == ["https://wallet.example/auth/callback"]
        assert request.headers["authorization"].startswith("Basic ")
        if not accepted:
            return httpx2.Response(400, json={"error": "invalid_grant"})
        return httpx2.Response(
            200,
            json={"access_token": "synthetic-token", "token_type": "Bearer"},
        )

    async def exchange():
        async with AsyncOAuth2Client(
            "synthetic-client",
            "synthetic-secret",
            redirect_uri="https://wallet.example/auth/callback",
            transport=httpx2.MockTransport(token_endpoint),
        ) as client:
            return await client.fetch_token(
                "https://issuer.example/token",
                code="synthetic-code",
                code_verifier=verifier,
            )

    if accepted:
        assert asyncio.run(exchange())["access_token"] == "synthetic-token"
    else:
        with pytest.raises(OAuthError, match="invalid_grant"):
            asyncio.run(exchange())
