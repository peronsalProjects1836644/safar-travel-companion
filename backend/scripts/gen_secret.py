"""Prints a random value for JWT_SECRET. Run: python -m scripts.gen_secret"""

import secrets

print(secrets.token_urlsafe(48))
