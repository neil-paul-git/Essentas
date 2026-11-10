import time
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientConnectionError

from app.core.config import Settings
from app.main import create_app
from app.providers.auth import SupabaseTokenVerifier, get_token_verifier


def test_me_returns_user_from_token(client, make_token) -> None:
    user_id = uuid4()
    token = make_token(sub=str(user_id))

    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"id": str(user_id), "email": "cook@example.com"}


def test_me_without_token_is_401(client) -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param({"exp": int(time.time()) - 60}, id="expired"),
        pytest.param({"aud": "anon"}, id="wrong-audience"),
        pytest.param({"iss": "https://evil.example.com/auth/v1"}, id="wrong-issuer"),
        pytest.param({"sub": "not-a-uuid"}, id="subject-not-a-uuid"),
        pytest.param({"key": "a-different-secret-that-is-32-bytes-long"}, id="bad-signature"),
    ],
)
def test_me_rejects_bad_tokens(client, make_token, claims) -> None:
    token = make_token(**claims)

    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_me_rejects_unsigned_token(client, make_token) -> None:
    token = make_token(key=None, algorithm="none")

    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


# --- Asymmetric (JWKS) mode: what newer Supabase projects use --------------------------


def _jwks_returning(public_key):
    """Stands in for PyJWKClient, so no network call is made."""
    return SimpleNamespace(get_signing_key_from_jwt=lambda token: SimpleNamespace(key=public_key))


def test_asymmetric_token_is_verified_with_public_key(make_token) -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    verifier = SupabaseTokenVerifier(
        Settings(supabase_jwt_secret=None), jwks_client=_jwks_returning(private_key.public_key())
    )
    user_id = str(uuid4())
    token = make_token(sub=user_id, key=private_key, algorithm="ES256", headers={"kid": "k1"})

    assert verifier.verify(token)["sub"] == user_id


def test_asymmetric_mode_rejects_hs256_token(make_token) -> None:
    """Algorithm confusion: an HS256 token must not pass where we expect ES256/RS256."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    verifier = SupabaseTokenVerifier(
        Settings(supabase_jwt_secret=None), jwks_client=_jwks_returning(private_key.public_key())
    )

    with pytest.raises(jwt.PyJWTError):
        verifier.verify(make_token())


def test_unreachable_jwks_is_503(make_token) -> None:
    class _Unreachable:
        def verify(self, token):
            raise PyJWKClientConnectionError("connection refused")

    app = create_app()
    app.dependency_overrides[get_token_verifier] = lambda: _Unreachable()

    with TestClient(app) as client:
        response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {make_token()}"})

    assert response.status_code == 503
