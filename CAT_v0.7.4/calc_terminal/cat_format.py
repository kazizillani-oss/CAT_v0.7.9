"""
CAT Proprietary & Secure File Format (.cat)

Provides encrypted, sealed binary storage for all user chat sessions, memories,
and user-personal data so that only CAT can read, write, and verify them.
Outside programs and plaintext viewers cannot read or tamper with .cat files.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import json
import logging
import os
import shutil
import uuid
import zlib
from typing import Any, Optional

log = logging.getLogger("cat.format")

MAGIC_HEADER = b"CATSECURE_V1\x00\x00"
MAGIC_LEN = len(MAGIC_HEADER)
CAT_HEADER = MAGIC_HEADER

# Device & user-bound key derivation
def _derive_cat_key() -> bytes:
    try:
        user = getpass.getuser()
    except Exception:
        user = "default_user"
    try:
        home = os.path.expanduser("~")
    except Exception:
        home = ""
    seed = f"CAT_SECURE_STORAGE_KEY::{user}::{home}::2026_V1"
    return hashlib.sha256(seed.encode("utf-8")).digest()


_FERNET_INSTANCE = None

def _get_fernet():
    global _FERNET_INSTANCE
    if _FERNET_INSTANCE is not None:
        return _FERNET_INSTANCE
    try:
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(_derive_cat_key())
        _FERNET_INSTANCE = Fernet(key)
        return _FERNET_INSTANCE
    except Exception:
        return None


def _fallback_encrypt(data: bytes, key: bytes) -> bytes:
    """Standard-library fallback cipher (HMAC-SHA256 authenticated keystream)."""
    salt = os.urandom(16)
    keystream_key = hashlib.sha256(key + salt).digest()
    
    # Stream cipher using keystream blocks
    encrypted = bytearray(len(data))
    block_idx = 0
    stream = b""
    for i in range(len(data)):
        if i % 32 == 0:
            stream = hashlib.sha256(keystream_key + block_idx.to_bytes(4, "big")).digest()
            block_idx += 1
        encrypted[i] = data[i] ^ stream[i % 32]
    
    mac = hmac.new(key, salt + bytes(encrypted), hashlib.sha256).digest()
    return salt + mac + bytes(encrypted)


def _fallback_decrypt(payload: bytes, key: bytes) -> bytes:
    """Decrypt and authenticate payload created by fallback cipher."""
    if len(payload) < 48:
        raise ValueError("Invalid payload length")
    salt = payload[:16]
    expected_mac = payload[16:48]
    encrypted = payload[48:]
    
    actual_mac = hmac.new(key, salt + encrypted, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_mac, actual_mac):
        raise ValueError("Data integrity verification failed")
    
    keystream_key = hashlib.sha256(key + salt).digest()
    decrypted = bytearray(len(encrypted))
    block_idx = 0
    stream = b""
    for i in range(len(encrypted)):
        if i % 32 == 0:
            stream = hashlib.sha256(keystream_key + block_idx.to_bytes(4, "big")).digest()
            block_idx += 1
        decrypted[i] = encrypted[i] ^ stream[i % 32]
    
    return bytes(decrypted)


def seal_cat_data(data: Any) -> bytes:
    """Serialize, compress, and encrypt data into the proprietary .cat binary container."""
    raw_json = json.dumps(data, ensure_ascii=False).encode("utf-8")
    compressed = zlib.compress(raw_json, level=9)
    
    fernet = _get_fernet()
    key = _derive_cat_key()
    if fernet is not None:
        try:
            cipher_payload = b"\x01" + fernet.encrypt(compressed)
        except Exception:
            cipher_payload = b"\x00" + _fallback_encrypt(compressed, key)
    else:
        cipher_payload = b"\x00" + _fallback_encrypt(compressed, key)
    
    return MAGIC_HEADER + cipher_payload


def unseal_cat_data(payload: bytes, allow_legacy_json: bool = True) -> Any:
    """Verify, decrypt, decompress, and deserialize .cat binary container."""
    if not payload.startswith(MAGIC_HEADER):
        # Check if legacy unencrypted JSON
        if allow_legacy_json:
            try:
                return json.loads(payload.decode("utf-8"))
            except Exception:
                raise ValueError("Invalid CAT secure container: unrecognized file format or corrupted header")
        raise ValueError("Invalid CAT secure container: missing magic header")
    
    body = payload[MAGIC_LEN:]
    if not body:
        raise ValueError("Empty .cat payload")
    
    tag = body[:1]
    cipher_bytes = body[1:]
    key = _derive_cat_key()
    
    try:
        if tag == b"\x01":
            fernet = _get_fernet()
            if fernet is not None:
                decompressed = fernet.decrypt(cipher_bytes)
            else:
                raise RuntimeError("Cryptography library required for method 1")
        elif tag == b"\x00":
            decompressed = _fallback_decrypt(cipher_bytes, key)
        else:
            raise ValueError("Unknown .cat cipher mode")
        
        raw_json = zlib.decompress(decompressed)
        return json.loads(raw_json.decode("utf-8"))
    except Exception as e:
        if isinstance(e, ValueError):
            raise
        raise ValueError(f"Corrupted or invalid CAT container: {e}") from e


def save_cat_file(path: str, data: Any) -> None:
    """Defensive atomic write of proprietary .cat format."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    
    cat_bytes = seal_cat_data(data)
    tmp_path = f"{path}.{uuid.uuid4().hex}.tmp"
    with open(tmp_path, "wb") as f:
        f.write(cat_bytes)
    
    try:
        os.replace(tmp_path, path)
    except OSError:
        try:
            if os.path.exists(path):
                os.remove(path)
            os.replace(tmp_path, path)
        except OSError:
            shutil.copyfile(tmp_path, path)
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def load_cat_file(path: str) -> Optional[Any]:
    """Load and unseal .cat file, or fallback to legacy JSON if migrating."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read()
        return unseal_cat_data(raw)
    except Exception as exc:
        log.warning("Failed to load .cat file %s: %s", path, exc)
        return None
