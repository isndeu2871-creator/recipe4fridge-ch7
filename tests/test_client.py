"""재시도와 예비 모델 전환 시험. 네트워크를 흉내 내서 쓴다."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import client  # noqa: E402


class FakeResponse:
    def __init__(self, status, body=None, text=""):
        self.status_code = status
        self._body = body if body is not None else {}
        self.text = text

    def json(self):
        return self._body


def ok_body(content="안녕"):
    return {"choices": [{"message": {"content": content}}]}


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(client.time, "sleep", lambda _: None)


def script(monkeypatch, responses):
    """정해 둔 응답을 차례로 돌려주는 가짜 post. 부른 모델 이름을 기록한다."""
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(json["model"])
        item = responses[min(len(calls) - 1, len(responses) - 1)]
        return item() if callable(item) else item

    monkeypatch.setattr(client.requests, "post", fake_post)
    return calls


# --- call_once ---

def test_call_once_returns_content(monkeypatch):
    script(monkeypatch, [FakeResponse(200, ok_body("hi"))])
    assert client.call_once("m", [], "key") == "hi"


def test_call_once_raises_on_error_status(monkeypatch):
    script(monkeypatch, [FakeResponse(429, {"error": {"message": "너무 잦음"}})])
    with pytest.raises(client.ModelError) as info:
        client.call_once("m", [], "key")
    assert info.value.status == 429


def test_call_once_raises_on_empty_choices(monkeypatch):
    """HTTP 200 인데 choices 가 비어 있는 경우 (노트 6.4.5.3목 c.2 의 KeyError)."""
    script(monkeypatch, [FakeResponse(200, {"choices": []})])
    with pytest.raises(client.ModelError) as info:
        client.call_once("m", [], "key")
    assert info.value.status == 200


def test_call_once_raises_on_blank_content(monkeypatch):
    """추론 모델이 max_tokens 를 다 써서 content 가 빈 경우."""
    script(monkeypatch, [FakeResponse(200, ok_body("   "))])
    with pytest.raises(client.ModelError):
        client.call_once("m", [], "key")


def test_call_once_omits_auth_header_without_key(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(headers)
        return FakeResponse(200, ok_body())

    monkeypatch.setattr(client.requests, "post", fake_post)
    client.call_once("m", [], None)
    assert "Authorization" not in seen


# --- call_with_fallback ---

def test_retries_same_model_on_429_then_succeeds(monkeypatch):
    responses = [FakeResponse(429, {"error": {"message": "x"}}),
                 FakeResponse(429, {"error": {"message": "x"}}),
                 FakeResponse(200, ok_body("됐다"))]
    calls = script(monkeypatch, responses)
    model, content, _ = client.call_with_fallback(["a", "b"], [], "key")
    assert content == "됐다"
    assert model == "a"
    assert calls == ["a", "a", "a"]


def test_moves_to_fallback_after_three_429(monkeypatch):
    responses = [FakeResponse(429, {"error": {"message": "x"}})] * 3 + [FakeResponse(200, ok_body())]
    calls = script(monkeypatch, responses)
    model, _, _ = client.call_with_fallback(["a", "b"], [], "key")
    assert model == "b"
    assert calls == ["a", "a", "a", "b"]


def test_404_skips_retry_and_goes_straight_to_fallback(monkeypatch):
    responses = [FakeResponse(404, {"error": {"message": "없음"}}), FakeResponse(200, ok_body())]
    calls = script(monkeypatch, responses)
    model, _, _ = client.call_with_fallback(["a", "b"], [], "key")
    assert model == "b"
    assert calls == ["a", "b"], "404 는 재시도 없이 바로 넘어가야 한다"


def test_raises_when_every_model_fails(monkeypatch):
    script(monkeypatch, [FakeResponse(404, {"error": {"message": "없음"}})])
    with pytest.raises(client.ModelError) as info:
        client.call_with_fallback(["a", "b", "c"], [], "key")
    assert "모든 모델" in str(info.value)


def test_log_records_each_attempt(monkeypatch):
    responses = [FakeResponse(404, {"error": {"message": "없음"}}), FakeResponse(200, ok_body())]
    script(monkeypatch, responses)
    _, _, log = client.call_with_fallback(["a", "b"], [], "key")
    joined = "\n".join(log)
    assert "선정 모델" in joined
    assert "예비 1" in joined
    assert "1차 시도" in joined


def test_on_event_is_called(monkeypatch):
    script(monkeypatch, [FakeResponse(200, ok_body())])
    seen = []
    client.call_with_fallback(["a"], [], "key", on_event=seen.append)
    assert seen and any("선정 모델" in line for line in seen)


# --- 빈 답일 때 토큰을 늘려 다시 시도 ---

def test_empty_answer_retries_same_model_with_bigger_budget(monkeypatch):
    """추론 모델이 토큰을 다 써서 빈 답이 오면 예산을 늘려 한 번 더 시도한다."""
    budgets = []

    def fake_post(url, headers=None, json=None, timeout=None):
        budgets.append(json["max_tokens"])
        if len(budgets) == 1:
            return FakeResponse(200, {"choices": [{"message": {"content": ""}}]})
        return FakeResponse(200, ok_body("됐다"))

    monkeypatch.setattr(client.requests, "post", fake_post)
    model, content, log = client.call_with_fallback(["a", "b"], [], "key", max_tokens=1000)
    assert model == "a", "같은 모델로 다시 시도해야 한다"
    assert content == "됐다"
    assert budgets == [1000, 4000]
    assert any("토큰으로 다시 시도" in line for line in log)


def test_budget_is_raised_only_once_then_moves_on(monkeypatch):
    budgets = []

    def fake_post(url, headers=None, json=None, timeout=None):
        budgets.append((json["model"], json["max_tokens"]))
        if json["model"] == "a":
            return FakeResponse(200, {"choices": [{"message": {"content": ""}}]})
        return FakeResponse(200, ok_body())

    monkeypatch.setattr(client.requests, "post", fake_post)
    model, _, _ = client.call_with_fallback(["a", "b"], [], "key", max_tokens=1000)
    assert model == "b"
    assert budgets == [("a", 1000), ("a", 4000), ("b", 1000)]
