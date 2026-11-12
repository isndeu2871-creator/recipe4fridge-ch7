"""PRD 3단계 — 회원, 프로필, 저장한 레시피.

`DATABASE_URL` 이 있으면 Supabase(Postgres), 없으면 내 PC 의 SQLite 를 쓴다.
배포한 앱을 다시 띄우면 SQLite 파일은 처음 상태로 돌아가므로 배포용은 Postgres 를 쓴다.
"""

import json
import os
import sqlite3
import threading
from pathlib import Path

from client import load_env

_LOCK = threading.Lock()
_SQLITE_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"


def database_url():
    load_env()
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        return url
    try:
        import streamlit as st

        return str(st.secrets.get("DATABASE_URL", "")).strip()
    except Exception:
        return ""


def is_postgres():
    return database_url().startswith(("postgres://", "postgresql://"))


def _connect():
    if is_postgres():
        import psycopg2

        # 잠든 앱이 깨어날 때 죽은 접속을 오래 기다리지 않게 한다 (노트 6.4.14.2).
        return psycopg2.connect(database_url(), connect_timeout=8,
                                options="-c tcp_user_timeout=8000")
    _SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(_SQLITE_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def _q(sql):
    """SQLite 는 ? 를, Postgres 는 %s 를 쓴다."""
    return sql.replace("?", "%s") if is_postgres() else sql


def run(sql, params=(), fetch=None):
    """질의 하나를 돌린다. fetch 는 None, "one", "all"."""
    with _LOCK:
        connection = _connect()
        try:
            cursor = connection.cursor()
            cursor.execute(_q(sql), params)
            if fetch == "one":
                row = cursor.fetchone()
                result = dict(zip([c[0] for c in cursor.description], row)) if row else None
            elif fetch == "all":
                names = [c[0] for c in cursor.description]
                result = [dict(zip(names, row)) for row in cursor.fetchall()]
            else:
                result = None
            connection.commit()
            return result
        finally:
            connection.close()


def init():
    serial = "SERIAL PRIMARY KEY" if is_postgres() else "INTEGER PRIMARY KEY AUTOINCREMENT"
    run(f"""CREATE TABLE IF NOT EXISTS users (
        id {serial},
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT DEFAULT '',
        auth_provider TEXT DEFAULT 'local'
    )""")
    run("""CREATE TABLE IF NOT EXISTS profiles (
        user_id INTEGER PRIMARY KEY,
        cuisine TEXT DEFAULT '한식',
        difficulty TEXT DEFAULT '초급',
        time_limit TEXT DEFAULT '30분 이내',
        servings INTEGER DEFAULT 2,
        vision_models TEXT DEFAULT '',
        text_models TEXT DEFAULT ''
    )""")
    run(f"""CREATE TABLE IF NOT EXISTS saved_recipes (
        id {serial},
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        payload TEXT NOT NULL
    )""")


# --- 회원 ---

def create_user(email, password_hash, provider="local"):
    run("INSERT INTO users (email, password_hash, auth_provider) VALUES (?, ?, ?)",
        (email, password_hash, provider))
    user = find_user(email)
    run("INSERT INTO profiles (user_id) VALUES (?)", (user["id"],))
    return user


def find_user(email):
    return run("SELECT * FROM users WHERE email = ?", (email,), fetch="one")


# --- 프로필 ---

def get_profile(user_id):
    profile = run("SELECT * FROM profiles WHERE user_id = ?", (user_id,), fetch="one")
    if profile is None:
        run("INSERT INTO profiles (user_id) VALUES (?)", (user_id,))
        profile = run("SELECT * FROM profiles WHERE user_id = ?", (user_id,), fetch="one")
    for key in ("vision_models", "text_models"):
        profile[key] = [m for m in (profile.get(key) or "").split(",") if m]
    return profile


def save_profile(user_id, cuisine, difficulty, time_limit, servings,
                 vision_models=(), text_models=()):
    run("""UPDATE profiles SET cuisine = ?, difficulty = ?, time_limit = ?,
           servings = ?, vision_models = ?, text_models = ? WHERE user_id = ?""",
        (cuisine, difficulty, time_limit, int(servings),
         ",".join(vision_models), ",".join(text_models), user_id))


# --- 저장한 레시피 ---

def save_recipe(user_id, recipe):
    run("INSERT INTO saved_recipes (user_id, title, payload) VALUES (?, ?, ?)",
        (user_id, recipe.get("title", "제목 없음"), json.dumps(recipe, ensure_ascii=False)))


def list_recipes(user_id):
    rows = run("SELECT id, title, payload FROM saved_recipes WHERE user_id = ? ORDER BY id DESC",
               (user_id,), fetch="all") or []
    for row in rows:
        row["recipe"] = json.loads(row["payload"])
    return rows


def delete_recipe(recipe_id, user_id):
    run("DELETE FROM saved_recipes WHERE id = ? AND user_id = ?", (recipe_id, user_id))
