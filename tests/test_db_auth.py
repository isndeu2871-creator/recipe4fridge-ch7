"""3단계(회원, 프로필, 저장) 시험. 임시 SQLite 파일을 쓴다."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import auth  # noqa: E402
import db  # noqa: E402


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_SQLITE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(db, "database_url", lambda: "")
    db.init()


# --- 비밀번호 ---

def test_hash_is_not_the_password_itself():
    stored = auth.hash_password("secret123")
    assert "secret123" not in stored


def test_same_password_hashes_differently_each_time():
    assert auth.hash_password("secret123") != auth.hash_password("secret123")


def test_verify_accepts_right_and_rejects_wrong():
    stored = auth.hash_password("secret123")
    assert auth.verify_password("secret123", stored)
    assert not auth.verify_password("secret124", stored)


def test_verify_rejects_empty_stored():
    assert not auth.verify_password("x", "")


# --- 가입과 로그인 ---

def test_sign_up_then_log_in():
    auth.sign_up("a@b.com", "password1")
    assert auth.log_in("a@b.com", "password1")["email"] == "a@b.com"


def test_email_is_lowercased():
    auth.sign_up("MiXeD@B.com", "password1")
    assert auth.log_in("mixed@b.com", "password1")


def test_rejects_bad_email():
    with pytest.raises(auth.AuthError):
        auth.sign_up("not-an-email", "password1")


def test_rejects_short_password():
    with pytest.raises(auth.AuthError):
        auth.sign_up("a@b.com", "short")


def test_rejects_duplicate_signup():
    auth.sign_up("a@b.com", "password1")
    with pytest.raises(auth.AuthError):
        auth.sign_up("a@b.com", "password2")


def test_rejects_unknown_user():
    with pytest.raises(auth.AuthError):
        auth.log_in("nobody@b.com", "password1")


def test_rejects_wrong_password():
    auth.sign_up("a@b.com", "password1")
    with pytest.raises(auth.AuthError):
        auth.log_in("a@b.com", "wrongpass")


# --- 구글 로그인 ---

def test_google_login_creates_user_once():
    first = auth.log_in_with_google("g@b.com")
    second = auth.log_in_with_google("g@b.com")
    assert first["id"] == second["id"]
    assert first["auth_provider"] == "google"


def test_google_user_cannot_use_password_form():
    """구글 회원이 이메일과 비밀번호 폼으로 들어오면 막는다 (노트 6.4.9.5목 d)."""
    auth.log_in_with_google("g@b.com")
    with pytest.raises(auth.AuthError) as info:
        auth.log_in("g@b.com", "anything123")
    assert "구글" in str(info.value)


# --- 프로필 ---

def test_profile_has_defaults_after_signup():
    user = auth.sign_up("a@b.com", "password1")
    saved = db.get_profile(user["id"])
    assert saved["cuisine"] == "한식"
    assert saved["servings"] == 2
    assert saved["vision_models"] == []


def test_profile_round_trip():
    user = auth.sign_up("a@b.com", "password1")
    db.save_profile(user["id"], "양식", "고급", "30분 이상", 4,
                    ["m1", "m2"], ["t1"])
    saved = db.get_profile(user["id"])
    assert saved["cuisine"] == "양식"
    assert saved["servings"] == 4
    assert saved["vision_models"] == ["m1", "m2"]
    assert saved["text_models"] == ["t1"]


# --- 저장한 레시피 ---

def sample(title="시금치 달걀볶음"):
    return {"title": title, "cuisine": "한식", "difficulty": "초급",
            "time_minutes": 15, "servings": 2, "used_ingredients": ["달걀"],
            "missing_ingredients": [], "steps": ["볶는다"]}


def test_save_and_list_recipe():
    user = auth.sign_up("a@b.com", "password1")
    db.save_recipe(user["id"], sample())
    rows = db.list_recipes(user["id"])
    assert len(rows) == 1
    assert rows[0]["recipe"]["steps"] == ["볶는다"]


def test_recipes_are_per_user():
    one = auth.sign_up("a@b.com", "password1")
    two = auth.sign_up("c@d.com", "password1")
    db.save_recipe(one["id"], sample())
    assert db.list_recipes(two["id"]) == []


def test_delete_recipe_only_by_owner():
    one = auth.sign_up("a@b.com", "password1")
    two = auth.sign_up("c@d.com", "password1")
    db.save_recipe(one["id"], sample())
    row_id = db.list_recipes(one["id"])[0]["id"]

    db.delete_recipe(row_id, two["id"])
    assert len(db.list_recipes(one["id"])) == 1, "남의 레시피를 지울 수 있으면 안 된다"

    db.delete_recipe(row_id, one["id"])
    assert db.list_recipes(one["id"]) == []
