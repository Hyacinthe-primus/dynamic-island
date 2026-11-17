"""Secrets at rest, encrypted with Windows DPAPI.

A protected value is stored as ``dpapi:<base64>``. Only the same Windows user on the same
machine can decrypt it, so a copied settings.json does not leak API keys. Values without the
prefix are legacy plain text and are returned as is, so callers can migrate them.
"""
import base64
import functools

PREFIX = "dpapi:"
_ENTROPY = b"DynamicIsland/credentials/v1"
_UI_FORBIDDEN = 0x01  # CRYPTPROTECT_UI_FORBIDDEN: never show a prompt


def is_protected(value):
    return isinstance(value, str) and value.startswith(PREFIX)


def protect(plain):
    """Encrypt a secret for the current Windows user ("" stays "")."""
    if not plain:
        return ""
    import win32crypt

    blob = win32crypt.CryptProtectData(plain.encode("utf-8"), "DynamicIsland", _ENTROPY,
                                       None, None, _UI_FORBIDDEN)
    return PREFIX + base64.b64encode(blob).decode("ascii")


@functools.lru_cache(maxsize=32)
def reveal(stored):
    """Decrypt a stored secret; "" if it cannot be decrypted (other user or machine, damaged)."""
    if not stored:
        return ""
    if not is_protected(stored):
        return stored
    import pywintypes
    import win32crypt

    try:
        _, data = win32crypt.CryptUnprotectData(base64.b64decode(stored[len(PREFIX):], validate=True),
                                                _ENTROPY, None, None, _UI_FORBIDDEN)
        return data.decode("utf-8")
    except (ValueError, pywintypes.error):
        return ""
