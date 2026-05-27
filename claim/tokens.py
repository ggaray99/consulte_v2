"""
Signed magic-link tokens for the claim flow.

We use TimestampSigner so the token is stateless: no separate token table,
no expiration cleanup. Tokens are valid for 24h.
"""

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner

CLAIM_TOKEN_MAX_AGE = 60 * 60 * 24  # 24 hours
SALT = 'consulte.claim.v1'


def _signer():
    return TimestampSigner(salt=SALT)


def make_claim_token(place_id, email):
    payload = f'{place_id}|{email.strip().lower()}'
    return _signer().sign(payload)


def read_claim_token(token):
    """Return (place_id:int, email:str) or raise ValueError on failure."""
    try:
        payload = _signer().unsign(token, max_age=CLAIM_TOKEN_MAX_AGE)
    except SignatureExpired:
        raise ValueError('expired')
    except BadSignature:
        raise ValueError('invalid')

    try:
        place_id_str, email = payload.split('|', 1)
        return int(place_id_str), email
    except (ValueError, AttributeError):
        raise ValueError('malformed')
