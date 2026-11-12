"""1단계 순수 로직 시험. 네트워크를 쓰지 않는다."""

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import client  # noqa: E402
import vision  # noqa: E402


def make_png(width, height):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="PNG")
    return buffer.getvalue()


# --- 사진 줄이기 (PRD 1단계 F2) ---

def test_resize_shrinks_long_edge():
    data = make_png(4000, 3000)
    _, original, new_size, before, after = vision.resize_image(data)
    assert original == (4000, 3000)
    assert max(new_size) == 1024
    assert new_size == (1024, 768)
    assert after < before


def test_resize_keeps_small_image_size():
    data = make_png(640, 480)
    _, _, new_size, _, _ = vision.resize_image(data)
    assert new_size == (640, 480)


def test_resize_handles_rgba():
    buffer = io.BytesIO()
    Image.new("RGBA", (200, 100), (255, 0, 0, 128)).save(buffer, format="PNG")
    jpeg, _, _, _, _ = vision.resize_image(buffer.getvalue())
    assert Image.open(io.BytesIO(jpeg)).format == "JPEG"


# --- 결과 다듬기 (PRD 1단계 F3, F5) ---

def test_normalize_fills_defaults():
    out = vision.normalize([{"name": "달걀"}])
    assert len(out) == 1
    assert {k: v for k, v in out[0].items() if k != "_id"} == {
        "name": "달걀", "quantity": 1, "unit": "개", "category": "기타"}


def test_normalize_accepts_plain_strings():
    assert vision.normalize(["우유"])[0]["name"] == "우유"


def test_normalize_rejects_unknown_unit_and_category():
    out = vision.normalize([{"name": "간장", "unit": "말", "category": "양념류"}])
    assert out[0]["unit"] == "기타"
    assert out[0]["category"] == "기타"


def test_normalize_coerces_quantity():
    assert vision.normalize([{"name": "사과", "quantity": "3"}])[0]["quantity"] == 3
    assert vision.normalize([{"name": "사과", "quantity": 2.7}])[0]["quantity"] == 2
    assert vision.normalize([{"name": "사과", "quantity": None}])[0]["quantity"] == 1
    assert vision.normalize([{"name": "사과", "quantity": 0}])[0]["quantity"] == 1


def test_normalize_drops_nameless_and_junk():
    assert vision.normalize([{"name": "  "}, 42, None, {"quantity": 2}]) == []


# --- JSON 꺼내기 ---

def test_parse_json_plain():
    assert client.parse_json('{"a": 1}') == {"a": 1}


def test_parse_json_fenced():
    assert client.parse_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_with_surrounding_text():
    assert client.parse_json('네, 결과입니다.\n{"a": 1}\n이상입니다.') == {"a": 1}


def test_parse_json_raises_without_object():
    with pytest.raises(ValueError):
        client.parse_json("JSON 이 없는 답")


# --- 오류 설명 ---

def test_explain_known_codes():
    assert "요청 제한" in client.explain(429)
    assert "인증" in client.explain(401)
    assert "찾을 수 없" in client.explain(404)
    assert "418" in client.explain(418)


# --- 중복 병합과 고유 id (노트 6.4.11.1목, 6.4.11.4목) ---

def test_normalize_merges_duplicate_names():
    out = vision.normalize([
        {"name": "달걀", "quantity": 3, "unit": "개"},
        {"name": "달걀", "quantity": 2, "unit": "개"},
        {"name": "우유", "quantity": 1, "unit": "팩"},
    ])
    assert len(out) == 2
    assert out[0]["name"] == "달걀" and out[0]["quantity"] == 5


def test_normalize_keeps_same_name_with_different_unit():
    out = vision.normalize([
        {"name": "우유", "quantity": 1, "unit": "팩"},
        {"name": "우유", "quantity": 500, "unit": "ml"},
    ])
    assert len(out) == 2


def test_normalize_gives_each_item_a_unique_id():
    out = vision.normalize([{"name": "달걀"}, {"name": "우유"}, {"name": "사과"}])
    ids = [item["_id"] for item in out]
    assert len(set(ids)) == 3


def test_deleting_middle_item_by_id_removes_the_right_one():
    """순번을 key 로 쓰면 가운데를 지울 때 마지막이 지워졌다 (노트 6.4.11.4목)."""
    items = vision.normalize([{"name": "달걀"}, {"name": "우유"}, {"name": "사과"}])
    target = items[1]["_id"]
    items = [i for i in items if i["_id"] != target]
    assert [i["name"] for i in items] == ["달걀", "사과"]
