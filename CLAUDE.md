# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 응답 언어

모든 답과 보고는 한국어로 한다.

## 저장소 성격

대학 수업(6장) 실습용. 냉장고 사진에서 식재료를 알아보고 레시피를 추천하는
Streamlit 앱을 3단계로 만든다. 세 단계 모두 구현되어 있고 배포만 남았다.

| 폴더 | 내용 |
| --- | --- |
| `docs/` | 단계별 PRD 세 개. 무엇을 만들지는 여기가 기준이다 |
| `src/` | `client.py` 모델 호출, `vision.py` 1단계, `recipe.py` 2단계, `db.py`·`auth.py` 3단계, `app.py` 화면 |
| `tests/` | 네트워크를 쓰지 않는 시험 |
| `screenshot/` | 단계별 작동 화면 |

`client.py` 와 `vision.py` 는 Streamlit 에 기대지 않는 순수 모듈이다.
화면 없이 시험할 수 있어야 하므로 여기에 `import streamlit` 을 넣지 않는다
(`client.get_api_key` 안의 선택적 import 만 예외).

## 모델 호출 규칙

모든 호출은 `client.call_with_fallback` 을 거친다. 직접 `requests.post` 를 쓰지 않는다.
이 함수가 세 가지를 맡는다.

1. 429/500/503 이면 10초, 20초 간격으로 3차까지 재시도
2. 404 등은 재시도 없이 바로 다음 모델
3. 빈 답이 오면 같은 모델에 토큰을 4배로 주어 한 번 더 시도

3번이 필요한 이유: 예비 모델 중 추론 모델이 있어 `max_tokens` 가 모자라면
생각하는 데 다 쓰고 빈 답을 돌려준다. 빈 답을 모델 탓으로 넘기기 전에 토큰부터 의심한다.

HTTP 200 인데 `choices` 가 비어 있는 경우가 실제로 있다. 앱이 죽지 않게 한다.

## 명령

```bash
pip install -r requirements.txt
streamlit run src/app.py                 # 앱 실행 (localhost:8501)
python -m pytest tests/ -q               # 시험
python3 test_openrouter.py               # 키 + 두 모델 연결 시험
```

학생은 윈도를 쓴다. 윈도에서는 `python3` 이 아니라 `python` 이고,
`run_test.bat` 을 더블클릭하는 방법도 있다. 명령을 안내할 때 윈도 쪽을 먼저 적는다.

`test_openrouter.py`는 테스트 프레임워크가 아니라 수동 실행 스크립트다.
텍스트 시험과 멀티모달 시험을 차례로 돌리고, 둘 다 통과하면 종료 코드 0,
하나라도 실패하면 1을 돌려준다. 개별 시험만 돌리려면 함수를 직접 호출한다.

```bash
python3 -c "import test_openrouter as t; t.test_text(t.get_api_key())"
python3 -c "import test_openrouter as t; t.test_vision(t.get_api_key())"
```

## 키 취급

`OPENROUTER_API_KEY`는 작업 폴더의 `.env`에만 둔다. `.gitignore`가 `.env`와
`.env.*`를 막고 `!.env.example`로 견본만 예외로 올린다. 스크립트는 외부
패키지 없이 `load_env()`로 `.env`를 직접 파싱하므로 python-dotenv를 넣지 않는다.
키가 없으면 안내 문구를 찍고 종료 코드 1로 끝난다.

## 모델 이름

수업에서 고른 모델 이름은 문자열 그대로 OpenRouter에 전달해야 하므로 바꾸지 않는다.
`test_openrouter.py` 위쪽의 `TEXT_MODEL`, `VISION_MODEL` 상수와 `.env.example`,
`README.md`의 표가 같은 값을 가리켜야 한다. 모델을 바꿀 때는 네 곳을 함께 고친다.

- 텍스트: `nvidia/nemotron-3-super-120b-a12b:free`
- 멀티모달: `google/gemma-4-26b-a4b-it:free`

두 모델 모두 2026-10-22 기준으로 호출이 막혀 있다(각각 404, 429). 그래서 코드는
`TEXT_MODELS`, `VISION_MODELS` 목록을 차례로 시도하고 404/429 면 예비로 넘어간다.
선정 모델은 1번 자리에 그대로 두어 살아나면 자동으로 다시 쓰이게 한다.
예비는 서로 다른 제공 업체로 섞는다. 같은 업체는 함께 막히기 때문이다.

`max_tokens` 를 제한할 때는 1500 이상으로 둔다. 예비 모델 중 추론 모델이 있어
작게 주면 생각하는 데 다 쓰고 빈 답을 돌려준다.

무료 모델은 목록에서 사라질 수 있다. 호출이 404나 400으로 실패하면 코드를 고치기 전에
OpenRouter 목록에서 `Prompt pricing`이 `FREE`인 상태로 남아 있는지 먼저 확인한다.

## 주의

클라우드 세션에서는 `openrouter.ai`로 나가는 요청이 프록시에서 403으로 막힌다.
실제 응답 시험은 학생 본인 PC에서 해야 하고, 여기서 확인할 수 있는 것은
`.env` 파싱, 그림 생성, 오류 처리 경로까지다.

## 화면을 고칠 때

- 재료 줄의 위젯 key 에는 순번이 아니라 재료의 `_id` 를 쓴다. 순번을 쓰면 가운데
  항목을 지울 때 엉뚱한 것이 지워진다 (노트 6.4.11.4목).
- 레시피 카드의 윗부분은 높이를 고정해 둔다. 풀면 부족한 재료가 긴 카드만
  버튼이 아래로 밀린다 (노트 6.4.9.1목 b.2).
- 로그아웃과 `처음부터` 는 `reset_flow()` 하나를 쓴다. 이전 화면이 남으면 안 된다.
- 주요 버튼 색은 `#D60000` 이다. Streamlit 기본 빨강은 명도 대비가 모자란다.

## 외부 설정이 없을 때의 동작

`DATABASE_URL` 이 없으면 SQLite, 구글 `[auth]` 설정이 없으면 로그인 버튼이 비활성이다.
설정이 없다고 앱이 죽으면 안 된다. 값을 넣는 쪽은 사람이 하고, 코드는 양쪽 모두에서 돌아야 한다.
