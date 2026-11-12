"""2단계(레시피 추천) 시험. 네트워크를 쓰지 않는다."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import recipe  # noqa: E402

ITEMS = [
    {"name": "달걀", "quantity": 3, "unit": "개"},
    {"name": "시금치", "quantity": 1, "unit": "봉지"},
]


# --- 프롬프트 ---

def test_prompt_lists_ingredients_with_amounts():
    text = recipe.build_prompt(ITEMS, "한식", "초급", "15분 이내", 2)
    assert "달걀 3개" in text
    assert "시금치 1봉지" in text


def test_prompt_carries_every_option():
    text = recipe.build_prompt(ITEMS, "양식", "고급", "30분 이상", 4)
    assert "양식" in text and "고급" in text and "30분 이상" in text and "4인분" in text


def test_prompt_demands_korean():
    """영문 레시피가 나오던 문제 (노트 6.4.11.1목)."""
    text = recipe.build_prompt(ITEMS, "한식", "초급", "15분 이내", 2)
    assert "한국어" in text
    assert "영어로 쓰지" in text


# --- 결과 다듬기 ---

def test_normalize_fills_missing_fields():
    out = recipe.normalize([{"title": "달걀말이"}], "한식", "초급", 2)
    assert out[0]["cuisine"] == "한식"
    assert out[0]["servings"] == 2
    assert out[0]["missing_ingredients"] == []
    assert out[0]["steps"] == []


def test_normalize_drops_untitled_and_junk():
    assert recipe.normalize([{"steps": ["x"]}, "문자열", None], "한식", "초급", 2) == []


def test_normalize_coerces_time():
    out = recipe.normalize([{"title": "a", "time_minutes": "25"}], "한식", "초급", 2)
    assert out[0]["time_minutes"] == 25
    out = recipe.normalize([{"title": "a", "time_minutes": "모름"}], "한식", "초급", 2)
    assert out[0]["time_minutes"] == 0


def test_normalize_drops_blank_steps():
    out = recipe.normalize([{"title": "a", "steps": ["볶는다", "  ", ""]}], "한식", "초급", 2)
    assert out[0]["steps"] == ["볶는다"]


# --- generate ---

def test_generate_rejects_empty_ingredients():
    with pytest.raises(ValueError):
        recipe.generate([], "한식", "초급", "15분 이내", 2, "key")


def test_generate_parses_model_answer(monkeypatch):
    answer = ('```json\n{"recipes": [{"title": "시금치 달걀볶음", '
              '"steps": ["재료를 씻는다", "볶는다", "담는다"], '
              '"missing_ingredients": ["참기름"]}]}\n```')
    monkeypatch.setattr(recipe, "call_with_fallback",
                        lambda *a, **k: ("fake-model", answer, ["기록"]))
    out = recipe.generate(ITEMS, "한식", "초급", "15분 이내", 2, "key")
    assert out["model"] == "fake-model"
    assert out["recipes"][0]["title"] == "시금치 달걀볶음"
    assert out["recipes"][0]["missing_ingredients"] == ["참기름"]


def test_generate_raises_when_no_recipe_in_answer(monkeypatch):
    monkeypatch.setattr(recipe, "call_with_fallback",
                        lambda *a, **k: ("m", '{"recipes": []}', []))
    with pytest.raises(ValueError):
        recipe.generate(ITEMS, "한식", "초급", "15분 이내", 2, "key")


def test_generate_uses_chosen_models(monkeypatch):
    seen = {}

    def fake(models, messages, api_key, max_tokens=None, on_event=None):
        seen["models"] = models
        return "m", '{"recipes": [{"title": "a"}]}', []

    monkeypatch.setattr(recipe, "call_with_fallback", fake)
    recipe.generate(ITEMS, "한식", "초급", "15분 이내", 2, "key", models=["only-this"])
    assert seen["models"] == ["only-this"]


def test_generate_falls_back_to_default_models(monkeypatch):
    seen = {}

    def fake(models, messages, api_key, max_tokens=None, on_event=None):
        seen["models"] = models
        return "m", '{"recipes": [{"title": "a"}]}', []

    monkeypatch.setattr(recipe, "call_with_fallback", fake)
    recipe.generate(ITEMS, "한식", "초급", "15분 이내", 2, "key", models=[])
    assert seen["models"] == recipe.TEXT_MODELS


# --- 상관없음 (교수님 앱의 선택지) ---

def test_any_is_first_option_everywhere():
    for options in (recipe.CUISINE_OPTIONS, recipe.DIFFICULTY_OPTIONS,
                    recipe.TIME_OPTIONS, recipe.SERVING_OPTIONS):
        assert options[0] == recipe.ANY


def test_any_conditions_are_left_out_of_the_prompt():
    """상관없음을 그대로 넣으면 모델이 그 말을 요리 종류로 읽는다."""
    text = recipe.build_prompt(ITEMS, recipe.ANY, recipe.ANY, recipe.ANY, recipe.ANY)
    assert recipe.ANY not in text
    assert "조건 없음" in text


def test_only_chosen_conditions_appear():
    text = recipe.build_prompt(ITEMS, "중식", recipe.ANY, "15분 이내", recipe.ANY)
    assert "종류: 중식" in text
    assert "조리 시간: 15분 이내" in text
    assert "난이도" not in text
    assert "인원" not in text


def test_normalize_does_not_write_any_into_a_recipe():
    out = recipe.normalize([{"title": "볶음밥"}], recipe.ANY, recipe.ANY, recipe.ANY)
    assert out[0]["cuisine"] == ""
    assert out[0]["difficulty"] == ""
    assert out[0]["servings"] == 2
