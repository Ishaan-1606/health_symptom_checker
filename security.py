from datetime import datetime, timedelta, timezone
from jose import jwt
from config import settings
import hashlib
import secrets
import base64
import typing

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

HASH_NAME = "sha256"
ITERATIONS = 200_000
SALT_LEN = 16
DKLEN = 32

def get_password_hash(password: str) -> str:
    """
    Create PBKDF2 password hash in this canonical form:
    pbkdf2_<hash_name>$<iterations>$<base64(salt)>$<base64(dk)>
    """
    if not password:
        raise ValueError("Password cannot be empty.")
    salt = secrets.token_bytes(SALT_LEN)
    dk = hashlib.pbkdf2_hmac(HASH_NAME, password.encode("utf-8"), salt, ITERATIONS, dklen=DKLEN)
    return f"pbkdf2_{HASH_NAME}${ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def _safe_b64decode(s: str) -> bytes:
    """Decode base64 while tolerating missing padding / whitespace."""
    s = s.strip()
    missing = len(s) % 4
    if missing:
        s += "=" * (4 - missing)
    return base64.b64decode(s)

def _verify_pbkdf2_components(hash_name: str, iterations: int, salt_b64: str, dk_b64: str, plain_password: str) -> bool:
    """
    Recompute PBKDF2-HMAC and compare with stored DK.
    Returns True if matches, False otherwise.
    """
    try:
        salt = _safe_b64decode(salt_b64)
        expected = _safe_b64decode(dk_b64)
    except Exception:
        return False
    new_dk = hashlib.pbkdf2_hmac(hash_name, plain_password.encode("utf-8"), salt, iterations, dklen=len(expected))
    return secrets.compare_digest(new_dk, expected)

def _split_concatenated_hashes(stored: str) -> typing.List[str]:
    """
    If the stored string contains multiple concatenated pbkdf2 entries,
    split them into candidates. Looks for occurrences of 'pbkdf2_' and 'pbkdf2$'.
    If none found, returns [stored].
    """
    candidates = []
    if not stored:
        return candidates
    marker = "pbkdf2_"
    if marker in stored:
        idxs = []
        start = 0
        while True:
            i = stored.find(marker, start)
            if i == -1:
                break
            idxs.append(i)
            start = i + len(marker)
        for i, sidx in enumerate(idxs):
            if i + 1 < len(idxs):
                candidates.append(stored[sidx:idxs[i+1]])
            else:
                candidates.append(stored[sidx:])
        return candidates
    marker2 = "pbkdf2$"
    if marker2 in stored:
        idxs = []
        start = 0
        while True:
            i = stored.find(marker2, start)
            if i == -1:
                break
            idxs.append(i)
            start = i + len(marker2)
        for i, sidx in enumerate(idxs):
            if i + 1 < len(idxs):
                candidates.append(stored[sidx:idxs[i+1]])
            else:
                candidates.append(stored[sidx:])
        return candidates
    return [stored]

def verify_password(plain_password: str, stored_hash: str) -> bool:
    """
    Verify plain_password against stored_hash.

    This function is tolerant and will:
    - accept the canonical 'pbkdf2_sha256$iter$salt$b64dk' format
    - accept legacy 'pbkdf2$sha256$iter$salt$b64dk'
    - accept 4-part 'sha256$iter$salt$b64dk'
    - detect and split concatenated repeated hashes and test each
    - return False on any parse/verification failure
    """
    if not plain_password or not stored_hash:
        return False
    candidates = _split_concatenated_hashes(stored_hash)
    for candidate in candidates:
        cand = candidate.strip()
        if cand.startswith("pbkdf2_"):
            parts = cand.split("$")
            if len(parts) >= 4:
                prefix_and_algo = parts[0] 
                if "_" in prefix_and_algo:
                    _, algo = prefix_and_algo.split("_", 1)
                else:
                    algo = HASH_NAME
                try:
                    iterations = int(parts[1])
                except Exception:
                    continue
                salt_b64 = parts[2]
                dk_b64 = parts[3]
                if _verify_pbkdf2_components(algo, iterations, salt_b64, dk_b64, plain_password):
                    return True
                else:
                    continue
        if cand.startswith("pbkdf2$"):
            parts = cand.split("$")
            if len(parts) >= 5:
                try:
                    _, algo, iterations_str, salt_b64, dk_b64 = parts[:5]
                    iterations = int(iterations_str)
                except Exception:
                    continue
                if _verify_pbkdf2_components(algo, iterations, salt_b64, dk_b64, plain_password):
                    return True
                else:
                    continue
        parts = cand.split("$")
        if len(parts) >= 4:
            try:
                algo, iterations_str, salt_b64, dk_b64 = parts[:4]
                iterations = int(iterations_str)
            except Exception:
                pass
            else:
                if _verify_pbkdf2_components(algo, iterations, salt_b64, dk_b64, plain_password):
                    return True
                else:
                    continue
        if cand.startswith("$2a$") or cand.startswith("$2b$") or cand.startswith("$2y$"):
            try:
                import bcrypt 
                if bcrypt.checkpw(plain_password.encode("utf-8"), cand.encode("utf-8")):
                    return True
            except Exception:
                continue
    return False
