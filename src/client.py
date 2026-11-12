"""OpenRouter 호출 공통 부분.

화면(Streamlit)과 떼어 두어 따로 시험할 수 있게 함.
"""

import json
import os
import time
from pathlib import Path

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 429 일 때 기다리는 간격(초). 1차 실패 -> 10초 -> 2차 실패 -> 20초 -> 3차
RETRY_DELAYS = (10, 20)


class ModelError(Exception):
    """한 모델 호출이 실패했음을 알림."""

    def __init__(self, status, message):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


def load_env(path=".env"):
    """작업 폴더의 .env 를 읽어 환경 변수로 올림."""
    for base in (Path.cwd(), Path(__file__).resolve().parent.parent):
        env_file = base / path
        if not env_file.exists():
            continue
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))
        return


def get_api_key():
    """키를 찾음. 배포 환경에서는 Streamlit Secrets 도 본다.

    키가 없고 프록시만 있으면 None 을 돌려준다. 그런 환경에서는 프록시가
    Authorization 헤더를 대신 붙여 준다.
    """
    load_env()
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        return key
    try:
        import streamlit as st

        key = str(st.secrets.get("OPENROUTER_API_KEY", "")).strip()
        if key:
            return key
    except Exception:
        pass
    if os.environ.get("HTTPS_PROXY"):
        return None
    raise ModelError(0, "OPENROUTER_API_KEY 를 찾지 못했습니다. .env 또는 Secrets 를 확인하세요.")


def explain(status):
    """오류 코드를 사람이 읽을 말로 바꿈 (노트 6.3.4.1목 b.2)."""
    return {
        200: "모델이 빈 답을 돌려주었습니다.",
        429: "일시적 요청 제한. 무료 모델에 요청이 몰렸습니다. 잠시 뒤 풀립니다.",
        403: "거절. 사용 한도를 넘었거나 크레딧 없이 유료 모델을 불렀습니다.",
        401: "인증 실패. API 키가 전달되지 않았거나 틀렸습니다.",
        404: "모델을 찾을 수 없습니다. 목록에서 사라졌을 수 있습니다.",
        500: "제공 업체 쪽 오류입니다.",
        503: "제공 업체가 잠시 쉬고 있습니다.",
    }.get(status, f"HTTP {status} 오류.")


def call_once(model, messages, api_key, max_tokens=2000, timeout=120):
    """한 모델을 부르고 본문 문자열을 돌려줌. 실패하면 ModelError.

    max_tokens 는 2000 이 기본이다. 예비 모델 중에 추론 모델이 있어
    작게 주면 생각하는 데 다 쓰고 빈 답을 돌려준다.
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.post(
        API_URL, headers=headers,
        json={"model": model, "messages": messages, "max_tokens": max_tokens},
        timeout=timeout,
    )
    if response.status_code != 200:
        try:
            detail = response.json()["error"]["message"]
        except Exception:
            detail = response.text[:200]
        raise ModelError(response.status_code, detail)

    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        # HTTP 200 인데 본문이 비어 있는 경우가 있다 (노트 6.4.5.3목 c.2 의 KeyError).
        raise ModelError(200, "응답에 choices 가 비어 있습니다.")
    content = (choices[0].get("message") or {}).get("content") or ""
    if not content.strip():
        raise ModelError(200, "응답 본문이 비어 있습니다. max_tokens 가 모자랐을 수 있습니다.")
    return content


def call_with_fallback(models, messages, api_key, max_tokens=2000, on_event=None):
    """모델 목록을 차례로 시도함. (쓴 모델, 본문, 기록) 을 돌려줌.

    429 면 같은 모델을 두 번 더 시도하고, 그래도 막히면 다음 모델로 넘어간다.
    404 등은 재시도 없이 바로 다음 모델로 넘어간다.
    """
    log = []

    def note(text):
        log.append(text)
        if on_event:
            on_event(text)

    last = None
    for index, model in enumerate(models):
        label = "선정 모델" if index == 0 else f"예비 {index}"
        budget = max_tokens
        grew = False
        attempt = 0
        while attempt < len(RETRY_DELAYS) + 1:
            attempt += 1
            try:
                note(f"[{label}] {model} — {attempt}차 시도")
                content = call_once(model, messages, api_key, budget)
                note(f"[{label}] {model} — 성공")
                return model, content, log
            except ModelError as error:
                last = error
                note(f"   실패 ({error.status}) {explain(error.status)}")

                # 추론 모델이 생각하는 데 토큰을 다 써서 답이 비는 경우가 있다.
                # 같은 모델에 토큰을 크게 주어 한 번 더 시도한다.
                if error.status == 200 and not grew:
                    grew = True
                    budget = max_tokens * 4
                    attempt -= 1
                    note(f"   추론에 토큰을 다 쓴 듯합니다. {budget} 토큰으로 다시 시도합니다")
                    continue

                if error.status not in (429, 500, 503) or attempt > len(RETRY_DELAYS):
                    break
                delay = RETRY_DELAYS[attempt - 1]
                note(f"   {delay}초 뒤 다시 시도합니다")
                time.sleep(delay)
        note(f"[{label}] {model} — 포기하고 다음 모델로 넘어갑니다")

    raise ModelError(getattr(last, "status", 0),
                     f"모든 모델이 실패했습니다. 마지막 오류: {getattr(last, 'message', '알 수 없음')}")


def parse_json(text):
    """모델이 돌려준 문자열에서 JSON 을 꺼냄.

    ```json 울타리나 앞뒤 설명이 붙어 와도 가운데 객체를 찾아낸다.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1]
        if cleaned.rstrip().endswith("```"):
            cleaned = cleaned.rstrip()[:-3]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        return json.loads(cleaned[start:end + 1])
    raise ValueError("JSON 을 찾지 못했습니다.")
