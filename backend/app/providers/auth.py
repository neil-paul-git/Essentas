"""Verifying access tokens (JWTs) issued by Supabase Auth."""

from functools import lru_cache
from typing import Any, Protocol

import jwt

from app.core.config import Settings, get_settings

# Supabase sets aud="authenticated" on signed-in users' tokens. The public anon key has a
# different audience, so checking it stops the anon key being used as a user token.
AUDIENCE = "authenticated"


class TokenVerifier(Protocol):
    def verify(self, token: str) -> dict[str, Any]:
        """Return the token's claims, or raise jwt.PyJWTError if it is not valid."""
        ...


class SupabaseTokenVerifier:
    def __init__(self, settings: Settings, jwks_client: Any = None) -> None:
        self._issuer = f"{settings.supabase_url.rstrip('/')}/auth/v1"
        self._secret = settings.supabase_jwt_secret or None
        self._jwks_client = jwks_client
        if self._secret is None and self._jwks_client is None:
            # Fetches Supabase's public keys on first use, then caches them.
            self._jwks_client = jwt.PyJWKClient(f"{self._issuer}/.well-known/jwks.json")

    def verify(self, token: str) -> dict[str, Any]:
        # The allowed algorithms are fixed by us, never taken from the token's header.
        # Otherwise an attacker could pick "none", or HS256 keyed with our public key.
        if self._secret is not None:
            key: Any = self._secret
            algorithms = ["HS256"]
        else:
            key = self._jwks_client.get_signing_key_from_jwt(token).key
            algorithms = ["ES256", "RS256"]

        return jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience=AUDIENCE,
            issuer=self._issuer,
            options={"require": ["exp", "sub", "aud", "iss"]},
        )


@lru_cache
def get_token_verifier() -> TokenVerifier:
    """One verifier per process, so fetched public keys stay cached. Overridden in tests."""
    return SupabaseTokenVerifier(get_settings())
