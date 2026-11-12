"""OpenRouter 키와 모델 연결 시험 (6.3.4 AI 모델 시험).

실행:  python3 test_openrouter.py
준비:  같은 폴더의 .env 에 OPENROUTER_API_KEY 를 저장해 둘 것
"""

import base64
import io
import json
import os
import sys
import time
from pathlib import Path

import requests

API_URL = "https://openrouter.ai/api/v1/chat/completions"
# 1번이 수업에서 선정한 모델. 404/429 로 막히면 예비 모델로 넘어감(노트 6.2.4.5/6.2.4.6).
TEXT_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",   # 수업 선정 모델
    "minimax/minimax-m3.1-flash:free",          # 예비 1 — 1.9초, 정확
    "openrouter/free",                          # 예비 2 — 1.4초, 정확
    "cohere/north-mini-code:free",              # 예비 3 — 10.1초, 정확
]
VISION_MODELS = [
    "google/gemma-4-26b-a4b-it:free",           # 수업 선정 모델
    "minimax/minimax-m3.1-flash:free",          # 예비 1 — 5.4초, 6/6
    "nvidia/nemotron-3.5-super-vl:free",        # 예비 2 — 12.4초, 6/6
    "dots-studio/dots-3-note-preview:free",     # 예비 3 — 11.3초, 6/6
]
TEXT_MODEL = TEXT_MODELS[0]
VISION_MODEL = VISION_MODELS[0]


def load_env(path=".env"):
    """.env 파일을 읽어 환경 변수로 올림 (추가 패키지 없이 처리)."""
    env_file = Path(__file__).resolve().parent / path
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def get_api_key():
    """키를 찾음. 없으면 None 을 돌려주고, 프록시가 헤더를 붙여주는 환경으로 간주함.

    - 보통(학생 PC): 같은 폴더의 .env 에서 읽음
    - 클라우드 세션: 네트워크 시크릿이 Authorization 헤더를 대신 붙여주므로 키가 없어도 됨
    """
    load_env()
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if key:
        print(f"[확인] 키를 읽었습니다: {key[:10]}...{key[-4:]} (길이 {len(key)})")
        return key
    if os.environ.get("HTTPS_PROXY"):
        print("[확인] .env 는 없지만 프록시가 있습니다. 네트워크 시크릿이 키를 붙여준다고 보고 진행합니다.")
        return None
    print("[실패] .env 에서 OPENROUTER_API_KEY 를 찾지 못했습니다.")
    print("       작업 폴더에 .env 파일이 있는지, 변수 이름이 맞는지 확인하세요.")
    sys.exit(1)


def explain_http_error(status):
    """노트 6.3.4.1목 b.2)의 오류 설명."""
    if status == 429:
        return (
            "429 일시적 요청 제한(Too Many Requests). 무료 모델에 요청이 몰릴 때 납니다. "
            "키가 잘못된 것이 아니므로 잠시 뒤 다시 실행하면 대개 풀립니다."
        )
    if status == 403:
        return (
            "403 거절. 키의 사용 한도를 넘었거나, 크레딧 없이 유료 모델을 부른 경우입니다. "
            "설정을 바꿔야 풀립니다. 모델 이름 끝에 :free 가 붙어 있는지 확인하세요."
        )
    if status == 401:
        return (
            "401 인증 실패. 키가 전달되지 않았습니다. "
            ".env 의 OPENROUTER_API_KEY 값을 확인하세요. "
            "클라우드 세션이라면 네트워크 시크릿을 저장한 뒤 새 세션에서 다시 실행해야 합니다."
        )
    if status == 404:
        return (
            "404 모델을 찾을 수 없음. 그 모델이 OpenRouter 목록에서 사라졌을 수 있습니다. "
            "openrouter.ai 에서 같은 이름이 FREE 로 남아 있는지 확인하세요."
        )
    return f"HTTP {status} 오류."


def ask(api_key, model, messages, timeout=120, retries=3):
    """429 가 나면 간격을 늘려가며 다시 시도함 (10초, 20초, 40초)."""
    delay = 10
    for attempt in range(1, retries + 1):
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        response = requests.post(
            API_URL, headers=headers,
            json={"model": model, "messages": messages},
            timeout=timeout,
        )
        if response.status_code == 429 and attempt < retries:
            print(f"      429 요청 제한 — {delay}초 뒤 다시 시도합니다 ({attempt}/{retries - 1})")
            time.sleep(delay)
            delay *= 2
            continue
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    raise RuntimeError("재시도를 모두 썼습니다.")


def ask_with_fallback(api_key, models, messages):
    """차례대로 시도하고, 404/429 면 다음 예비 모델로 넘어감. (쓴 모델, 답) 을 돌려줌."""
    last = None
    for index, model in enumerate(models):
        label = "선정 모델" if index == 0 else f"예비 {index}"
        print(f"   [{label}] {model}")
        try:
            return model, ask(api_key, model, messages)
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else 0
            print(f"      건너뜀 — {explain_http_error(status).split('.')[0]}")
            last = error
            if status not in (404, 429):
                raise
    raise last


def test_text(api_key):
    print("\n[1] 텍스트 모델 시험")
    prompt = (
        "다음 문장에서 재료를 뽑아 JSON 으로만 답하세요. "
        '형식: {"ingredients": ["...", "..."]}. 설명은 쓰지 마세요.\n'
        "문장: 냉장고에 달걀 3개, 우유 반 통, 시금치 한 봉지가 있어."
    )
    used, answer = ask_with_fallback(api_key, TEXT_MODELS, [{"role": "user", "content": prompt}])
    print(f"   쓴 모델: {used}")
    print("   응답 원문:", answer.strip()[:300])

    cleaned = answer.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        print("[주의] JSON 으로 바로 바뀌지 않았습니다. 모델은 응답했으나 형식이 어긋납니다.")
        return False
    print("[성공] JSON 처리 확인:", data)
    return True


def make_test_image():
    """도형(빨간 원)과 문자(AI)가 그려진 작은 PNG 를 만들어 base64 로 돌려줌."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (256, 256), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 40, 216, 216), fill="red")
    draw.text((105, 115), "AI", fill="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def test_vision(api_key):
    print("\n[2] 멀티모달 모델 시험")
    try:
        encoded = make_test_image()
    except ImportError:
        print("[건너뜀] pillow 가 없습니다.  python3 -m pip install pillow")
        return False

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "이 그림에 보이는 도형의 모양과 색, 그리고 적힌 글자를 한국어로 짧게 알려주세요.",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{encoded}"},
                },
            ],
        }
    ]
    used, answer = ask_with_fallback(api_key, VISION_MODELS, messages)
    print(f"   쓴 모델: {used}")
    print("   응답 원문:", answer.strip()[:300])

    text = answer.lower()
    ok = ("원" in answer or "circle" in text) and ("빨" in answer or "red" in text)
    print("[성공] 그림을 읽었습니다." if ok else "[주의] 모델은 응답했으나 도형/색을 정확히 맞추지 못했습니다.")
    return ok


def main():
    api_key = get_api_key()
    results = []
    for name, func in (("텍스트", test_text), ("멀티모달", test_vision)):
        try:
            results.append((name, func(api_key)))
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else 0
            print(f"[실패] {explain_http_error(status)}")
            if error.response is not None:
                print(f"       서버 응답: {error.response.text[:200]}")
            results.append((name, False))
        except requests.RequestException as error:
            print(f"[실패] 통신 오류: {error}")
            results.append((name, False))

    print("\n=== 시험 결과 ===")
    for name, ok in results:
        print(f"{name}: {'성공' if ok else '확인 필요'}")
    if not all(ok for _, ok in results):
        print("\n실패한 시험이 429 였다면 잠시 뒤 이 프로그램을 다시 실행하세요.")
    sys.exit(0 if all(ok for _, ok in results) else 1)


if __name__ == "__main__":
    main()
