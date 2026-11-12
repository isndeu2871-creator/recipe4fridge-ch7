"""PRD 3단계 — 로그인과 회원 가입.

비밀번호는 해시로만 저장한다. 원문을 두지 않는다.
구글 로그인은 Streamlit 의 `st.login` 을 쓰며, 설정이 없으면 버튼을 비활성으로 둔다.
"""

import hashlib
import hmac
import os
import re

import db

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 8
_ITERATIONS = 120_000


class AuthError(Exception):
    pass


def hash_password(password, salt=None):
    salt = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS)
    return f"{salt}${digest.hex()}"


def verify_password(password, stored):
    if not stored or "$" not in stored:
        return False
    salt, _ = stored.split("$", 1)
    return hmac.compare_digest(hash_password(password, salt), stored)


def validate(email, password):
    if not EMAIL_RE.match(email or ""):
        raise AuthError("이메일 모양이 올바르지 않습니다.")
    if len(password or "") < MIN_PASSWORD:
        raise AuthError(f"비밀번호는 {MIN_PASSWORD}자 이상이어야 합니다.")


def sign_up(email, password):
    email = (email or "").strip().lower()
    validate(email, password)
    if db.find_user(email):
        raise AuthError("이미 가입된 이메일입니다.")
    return db.create_user(email, hash_password(password), "local")


def log_in(email, password):
    email = (email or "").strip().lower()
    user = db.find_user(email)
    if user is None:
        raise AuthError("가입되지 않은 이메일입니다.")
    if user["auth_provider"] == "google":
        # 구글로 가입한 회원은 비밀번호가 없으므로 이 폼으로 들어올 수 없다.
        raise AuthError("구글로 가입한 계정입니다. `Google로 로그인` 을 쓰세요.")
    if not verify_password(password, user["password_hash"]):
        raise AuthError("비밀번호가 맞지 않습니다.")
    return user


def log_in_with_google(email):
    """구글이 확인해 준 이메일로 회원을 찾거나 새로 만든다."""
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AuthError("구글에서 이메일을 받지 못했습니다.")
    return db.find_user(email) or db.create_user(email, "", "google")


def google_ready():
    """구글 로그인 설정이 되어 있는지 본다."""
    try:
        import streamlit as st

        return bool(st.secrets.get("auth", {}).get("client_id"))
    except Exception:
        return False
