"""Security placeholders.

Step 2 adds argon2id password hashing and JWT access tokens. Refresh tokens
will be stored only as a SHA-256 hash. This module stays free of those
libraries until that step needs them.
"""
