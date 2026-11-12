# Study_04 — 냉장고 레시피 추천 앱 (6장)

클로드 데스크톱 작업 폴더. OpenRouter API 키를 안전하게 쓰기 위한 준비와
수업에서 선정한 모델 정보를 남겨 둔 폴더임.

## 1. 키 보관 규칙

| 파일 | 역할 | 깃허브 업로드 |
| --- | --- | --- |
| `.env` | 실제 API 키를 담는 파일 | ❌ (`.gitignore`로 차단) |
| `.env.example` | 키 값을 뺀 변수 이름 견본 | ✅ |

`.env`는 이 폴더에 직접 만들고, 다음 한 줄만 넣으면 됨.

```
OPENROUTER_API_KEY=sk-or-v1-...
```

`.gitignore` 규칙 설명

- `.env` : 키를 저장한 파일을 올리지 않음
- `.env.*` : `.env.local` 처럼 `.env.` 로 시작하는 다른 키 파일도 올리지 않음
- `!.env.example` : 앞의 `!` 는 예외. 키 값을 뺀 견본은 올림
- `.DS_Store` : 동기화 앱이 폴더마다 만드는 숨김 파일을 올리지 않음

파일 권한도 본인만 읽도록 좁혀 두는 것이 안전함.

```bash
chmod 600 .env
```

## 2. 모델 선정

- OpenRouter 목록에서 **`Prompt pricing` 이 `FREE`** 인지 꼭 확인함
- `google/gemma-4-26b-a4b-it:free` 는 멀티모달 모델이므로 이미지 쪽 목록에도 같이 보임
- 우리 수업의 텍스트 모델: **`nvidia/nemotron-3-super-120b-a12b:free`**
- 선정한 모델 이름은 그대로 복사해서 보관해야 함. 나중에 오픈라우터에 이 문자열을 그대로 전달함
- 모델 목록은 바뀔 수 있으므로, 실습하는 날 같은 조건(무료·텍스트)으로 목록에 남아 있는지 다시 확인함

### 이미지(멀티모달) 모델 — 6.2.4.5

`Input Modalities` 에서 `Image` 를 골라 찾음. 냉장고 사진에서 식재료를 알아보는 데 씀.
`예비` 는 앞 모델이 막히면 넘어가는 모델임.

| 구분 | 차례 | 모델 |
| --- | --- | --- |
| 7월 실습의 캡처 | 1 | `google/gemma-4-31b-it:free` |
|  | 예비 | `nvidia/nemotron-nano-12b-v2-vl:free` |
| 이 노트에서 쓰는 모델 | 1 | `google/gemma-4-26b-a4b-it:free` |
| 시연 영상과 시연 앱 | 1 | `google/gemma-4-26b-a4b-it:free` |
|  | 예비 1 | `nvidia/nemotron-3.5-super-vl:free` |
|  | 예비 2 | `dots-studio/dots-3-note-preview:free` |
|  | 예비 3 | `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` |
| 노트 앱의 최종 코드 | 1 | `minimax/minimax-m3:free` |
|  | 2 | `google/gemma-4-26b-a4b-it:free` |
|  | 3 | `google/gemma-4-31b-it:free` |
|  | 그 뒤 | 그 밖의 무료 비전 모델(무작위 순서) |

### 텍스트 모델 — 6.2.4.6

`Input Modalities` 에서 `Text` 만 고르고 `Image` 는 해제함. 식재료로 레시피를 추천하는 데 씀.

#### 자료별 비교 (2026-10-21 기준)

| 구분 | 차례 | 모델 |
| --- | --- | --- |
| 7월 실습의 캡처 | 1 | `openai/gpt-oss-20b:free` |
| 이 노트에서 쓰는 모델 | 1 | `nvidia/nemotron-3-super-120b-a12b:free` |
| 시연 영상과 시연 앱 | 1 | `nvidia/nemotron-3-super-120b-a12b:free` |
| 노트 앱의 최종 코드 | 1 | `minimax/minimax-m3:free` |
|  | 2 | `nvidia/nemotron-3-super-120b-a12b:free` |
|  | 3 | `cohere/north-mini-code:free` |
|  | 그 뒤 | 그 밖의 무료 텍스트 모델(무작위 순서) |

노트 앱은 프로필 화면에서 고른 모델 안에서만 위 차례로 시도함.

## 3. 연결 시험 (6.3.4 AI 모델 시험)

`.env` 를 만든 뒤 아래를 실행함.

**윈도** — 탐색기에서 `run_test.bat` 을 더블클릭하면 설치와 시험을 한 번에 처리함.
명령 프롬프트에서 직접 치려면 다음과 같이 함.

```
python -m pip install requests pillow
python test_openrouter.py
```

**맥 / 리눅스**

```bash
python3 -m pip install requests pillow
python3 test_openrouter.py
```

시험 내용 두 가지

1. 텍스트 모델에 문장을 보내고 **JSON 형식**으로 제대로 답하는지 확인
2. 멀티모달 모델에 **도형과 문자**가 그려진 그림을 보내고 제대로 읽어내는지 확인

둘 다 `[성공]` 이 나오면 키와 모델이 정상임.

클로드에게 시켜서 시험할 때는 노트 6.3.4.1목의 프롬프트를 씀.

```
이제 준비된 API가 실제로 작동하는지 테스트해 줘.
이미지 인식은 google/gemma-4-26b-a4b-it:free 모델을 이용하고,
텍스트 인식은 nvidia/nemotron-3-super-120b-a12b:free 모델을 이용할 거야.
API를 통한 텍스트와 이미지 인식을 각각 테스트해서 실행 결과를 알려줘.
```

### 오류가 났을 때

| 코드 | 뜻 | 대처 |
| --- | --- | --- |
| `429` | 일시적 요청 제한. 무료 모델에 요청이 몰림 | 키 문제가 아님. 스크립트가 10초·20초 간격으로 두 번 더 시도하고, 그래도 안 되면 잠시 뒤 다시 실행 |
| `403` | 거절. 사용 한도 초과이거나 크레딧 없이 유료 모델 호출 | 모델 이름 끝에 `:free` 가 붙어 있는지 확인. 설정을 바꿔야 풀림 |
| `401` | 인증 실패 | `.env` 의 키 값이 틀렸거나 만료됨 |
| `404` | 모델 없음 | 그 모델이 목록에서 사라짐. 위 표의 예비 모델로 바꿔서 시도 |

텍스트는 성공했는데 이미지만 `429` 로 실패하는 경우가 흔함. 제공 업체 쪽이 혼잡한 것이고
시간이 지나면 풀리므로, 코드를 고치지 말고 다시 실행함.

## 4. 이 저장소의 파일

| 파일 | 역할 |
| --- | --- |
| `.gitignore` | 키 파일을 깃허브에 올리지 않게 막는 규칙 |
| `.env.example` | 키 값을 뺀 변수 이름 견본 |
| `CLAUDE.md` | 클로드에게 주는 이 폴더의 안내 (응답 언어, 명령, 키 취급 규칙) |
| `test_openrouter.py` | 키와 두 모델의 연결 시험 |
| `run_test.bat` | 윈도에서 더블클릭으로 시험을 실행하는 파일 |

`.env` 는 이 목록에 없음. 각자 본인 컴퓨터에서 만들고 깃허브에는 올리지 않음.

## 5. 실행 확인 기록 (2026-10-22)

클라우드 세션에서 실제로 호출해 확인한 결과임.

```
[1] 텍스트 모델 시험
   [선정 모델] nvidia/nemotron-3-super-120b-a12b:free
      건너뜀 — 404 모델을 찾을 수 없음
   [예비 1] cohere/north-mini-code:free
   응답 원문: {"ingredients": ["eggs", "milk", "spinach"]}
[성공] JSON 처리 확인

[2] 멀티모달 모델 시험
   [선정 모델] google/gemma-4-26b-a4b-it:free
      건너뜀 — 429 일시적 요청 제한
   [예비 1] nvidia/nemotron-3.5-super-vl:free
   응답 원문: 모양: 원형 / 색: 빨간색 (글자는 흰색) / 적힌 글자: AI
[성공] 그림을 읽었습니다
```

### 이 날짜 기준 모델 상태

| 모델 | 결과 |
| --- | --- |
| `nvidia/nemotron-3-super-120b-a12b:free` | 404 — 목록에는 있으나 제공 업체가 거절 |
| `google/gemma-4-26b-a4b-it:free` | 429 — 업체 혼잡, 시간이 지나면 풀릴 수 있음 |
| `cohere/north-mini-code:free` | 정상 |
| `nvidia/nemotron-3.5-super-vl:free` | 정상 |
| `dots-studio/dots-3-note-preview:free` | 정상 |
| `google/gemma-4-31b-it:free` | 429 |
| `minimax/minimax-m3:free` | 무료 중단, 유료로 바뀜 |
| `openai/gpt-oss-20b:free` | 무료 중단, 유료로 바뀜 |

목록에 `FREE` 로 보이는 것과 실제로 호출이 되는 것은 다름. 실습일에 이 스크립트를 한 번
돌려 보는 것이 목록을 눈으로 확인하는 것보다 확실함.

## 6. 무료 모델 전수 시험 (2026-10-22)

OpenRouter 무료 모델 21개(텍스트 21, 이미지 12)를 실제로 호출해 시험함.

- 텍스트 과제: 한국어 문장에서 재료 3개를 뽑아 JSON 으로 답하기
- 이미지 과제: 빨간 원 + 파란 사각형 + `AI 2026` 글자를 읽기 (6점 만점)

### 텍스트 결과 (합격 = JSON + 한국어 + 3개 정확)

| 모델 | 시간 | 결과 |
| --- | --- | --- |
| `openrouter/free` | 1.4초 | 합격 |
| `recursive/flint-v1.0:free` | 1.5초 | 합격 |
| `poolside/laguna-xs-2.1:free` | 1.9초 | 합격 |
| `minimax/minimax-m3.1-flash:free` | 1.9초 | 합격 |
| `nvidia/nemotron-3.5-super-vl:free` | 3.6초 | 합격 |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | 8.1초 | 합격 |
| `cohere/north-mini-code:free` | 10.1초 | 합격 |
| `liquid/lfm-2.5-2.6b:free` | 13.2초 | 합격 |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 44.4초 | 달걀을 "계산"으로 오인 |
| `poolside/laguna-s-2.1:free` | 5.4초 | JSON 미완성 |
| `nvidia/nemotron-3-super-120b-a12b:free` | — | 404 |
| `google/gemma-4-26b-a4b-it:free`, `google/gemma-4-31b-it:free` | — | 429 |
| `thinkingmachines/inkling*:free` | — | 403 유료 전용 |

### 이미지 결과

| 모델 | 시간 | 점수 |
| --- | --- | --- |
| `minimax/minimax-m3.1-flash:free` | 5.4초 | 6/6 |
| `openrouter/free` | 8.3초 | 6/6 |
| `dots-studio/dots-3-note-preview:free` | 11.3초 | 6/6 |
| `nvidia/nemotron-3.5-super-vl:free` | 12.4초 | 6/6 |
| `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` | 36.3초 | 6/6 |
| `google/gemma-4-26b-a4b-it:free`, `google/gemma-4-31b-it:free` | — | 429 |

### 적용한 차례

`openrouter/free` 는 특정 모델이 아니라 그때그때 알아서 골라주는 라우터임.
결과를 예측하기 어려워 예비 2번에 둠.

| 구분 | 차례 | 모델 | 이유 |
| --- | --- | --- | --- |
| 텍스트 | 1 | `nvidia/nemotron-3-super-120b-a12b:free` | 수업 선정. 지금은 404 지만 살아나면 자동으로 다시 쓰임 |
|  | 2 | `minimax/minimax-m3.1-flash:free` | 빠르고 정확, 이미지도 됨 |
|  | 3 | `openrouter/free` | 가장 빠름 |
|  | 4 | `cohere/north-mini-code:free` | 다른 업체라 같이 막힐 일이 적음 |
| 이미지 | 1 | `google/gemma-4-26b-a4b-it:free` | 수업 선정. 지금은 429 |
|  | 2 | `minimax/minimax-m3.1-flash:free` | 가장 빠르고 만점 |
|  | 3 | `nvidia/nemotron-3.5-super-vl:free` | 만점 |
|  | 4 | `dots-studio/dots-3-note-preview:free` | 만점 |

예비는 서로 다른 제공 업체로 섞음. 같은 업체는 함께 막히기 때문임
(이번 시험에서 구글 모델 두 개가 동시에 429 였음).

### 추론 모델 주의

`nemotron-3.5-super-vl`, `dots-3-note-preview`, `openrouter/free` 는 답하기 전에 생각하는
추론 모델임. `max_tokens` 를 작게 주면 생각하는 데 다 써서 **빈 답**이 돌아옴.
처음 시험에서 200 으로 주었다가 셋 다 빈 답을 받았고, 1500 으로 올리니 모두 만점이었음.
`max_tokens` 를 제한할 거라면 1500 이상으로 둘 것.

## 7. 앱 (6.4절)

### 폴더

| 폴더 | 내용 |
| --- | --- |
| `docs/` | `PRD_step1.md`, `PRD_step2.md`, `PRD_step3.md` |
| `src/` | `client.py` (모델 호출), `vision.py` (1단계 인식), `app.py` (화면) |
| `tests/` | 네트워크를 쓰지 않는 시험 |
| `screenshot/` | 작동 화면 캡처 |

### 실행

```
pip install -r requirements.txt       # 앱 실행용
pip install -r requirements-dev.txt   # 시험까지 돌리려면
streamlit run src/app.py
```

`http://localhost:8501` 로 열린다. 배포는 Streamlit Community Cloud 를 쓰고,
키는 `Settings` → `Secrets` 에 `OPENROUTER_API_KEY` 로 넣는다.

### 시험

```
python -m pytest tests/ -q
```

### 진행 상태

| 단계 | 상태 |
| --- | --- |
| PRD 3개 | 완료 |
| 1단계 식재료 인식 | 완료 |
| 2단계 레시피 추천 | 완료 |
| 3단계 프로필과 저장 | 완료 (SQLite. Supabase 는 `DATABASE_URL` 만 넣으면 됨) |
| 배포 | 아직 |

### 화면 구성

```
사이드바   app / 내 레시피 / 프로필
          로그인 · 회원가입 · Google로 로그인
머리말     ✅ ① 사진 업로드    ✅ ② 식재료 확인    ③ 레시피 추천
          오른쪽 위 `🔄 처음부터`

1단계      ① 사진 업로드
2단계      ① 사진 업로드  |  ② 식재료 확인
3단계      ② 식재료 확인  |  ③ 레시피 추천
```

단계를 넘겨도 화면을 갈아 끼우지 않고 **두 칸으로 나란히** 둔다. 사진과 재료가,
재료와 레시피가 맞는지 한 화면에서 볼 수 있어야 하기 때문이다 (노트 6.4.11.3목).
지난 단계에는 머리말에 `✅` 가 붙는다.

3단계의 조건 네 개는 모두 `상관없음` 을 고를 수 있다. `상관없음` 은 프롬프트에
넣지 않는다. 넣으면 모델이 그 말을 요리 종류로 읽는다.

레시피 카드의 `자세히 보기` 를 누르면 카드 아래에 상세 칸이 열린다.
`← 목록으로` 로 닫고, `레시피 저장` 으로 저장한다.

### 노트의 개선 목록 반영 (6.4.9 ~ 6.4.11)

| 항목 | 반영 |
| --- | --- |
| 끌어 놓기 업로드 | `st.file_uploader` 가 기본 지원 |
| 수량 단위 드롭다운 | `개/병/봉지/팩/단/g/kg/ml/L/기타` |
| 3차 시도 후 예비 모델 | `client.call_with_fallback` |
| 레시피 쪽도 같은 재시도 | 같은 함수를 씀 |
| `자세히 보기` 세로 위치 | 카드 윗부분 높이를 210px 로 고정. 좌표로 확인함 |
| 버튼 누르지 않아도 자동 생성 | 2단계에서 넘어오면 바로 만듦 |
| 재료를 회색 타원으로 한 줄 | `.chip` |
| 조건 드롭다운 4개 | 종류·난이도·조리 시간·인원 |
| 부족한 재료 표시 | 카드마다 표시 |
| 이전 단계로 이동 | `← 이전`, `처음부터` |
| 한국어 레시피 | 프롬프트에 명시. 시험으로 확인 |
| 중복 재료 병합 | 같은 이름·단위면 수량을 합침 |
| 가운데 재료 삭제 버그 | 위젯 key 에 순번 대신 고유 `_id` |
| 로그아웃 시 화면 초기화 | `reset_flow()` |
| 명도 대비 | 주요 버튼 `#D60000` (5.44:1) |
| 터치 크기 | 누르는 단추 최소 높이 44px |
| 프로필에서 모델 고르기 | 프로필 화면의 `AI 모델 선택` |

### 아직 하지 않은 것

- Streamlit Community Cloud 배포 (교수님 계정 로그인이 필요함)
- Supabase 연결 (`DATABASE_URL` 이 없어 SQLite 로 돎)
- 구글 로그인 (`[auth]` 설정이 없어 버튼이 비활성)

셋 다 외부 계정 설정이라 코드는 준비돼 있고 값만 넣으면 됨.

### 1단계에서 겪은 것

- **추론 모델의 토큰 부족**: `max_tokens` 를 2000 으로 주었더니 예비 모델들이 빈 답을
  돌려주었음. 추론에 토큰을 다 쓴 것이었음(`nemotron-3.5-super-vl` 은 간단한 그림에도
  추론에만 653 토큰을 씀). 기본값을 4000 으로 올리고, 빈 답이 오면 같은 모델에
  4배로 주어 한 번 더 시도하게 함
- **선정 모델의 429**: `google/gemma-4-26b-a4b-it:free` 는 시험한 내내 429 였음.
  3차까지 시도한 뒤 예비 1(`minimax/minimax-m3.1-flash:free`)로 넘어가 성공함
- **오인식**: 주황색 `JUICE` 통을 "고기", 다음 시도에서는 "맥주"로 읽었음.
  노트 6.4.9.1목 c.3 의 "무료 모델의 한계" 가 그대로 나타남. 그래서 결과를
  손으로 고칠 수 있게 두는 것이 중요함

## 8. Streamlit Community Cloud 배포 (6.4.8)

### Deploy an app 화면에 넣을 값

| 칸 | 값 |
| --- | --- |
| Repository | `isndeu2871-creator/Study_04` |
| Branch | `claude/loving-rubin-zb0ths` |
| Main file path | `src/app.py` |
| App URL | 아직 아무도 안 쓰는 이름 |

### 배포 뒤 Secrets

`Settings` → `Secrets` 에 아래를 넣는다. `.env` 는 깃허브에 올라가지 않으므로
배포 서버에는 키가 없다. 넣지 않으면 앱은 뜨지만 인식이 실패한다.

```toml
OPENROUTER_API_KEY = "sk-or-v1-본인키"
```

Supabase 와 구글 로그인을 쓸 때 더 넣는 값. `[auth]` 아래에 적은 줄은 모두
`[auth]` 에 속하므로 `DATABASE_URL` 을 그 아래에 두지 않는다.

```toml
OPENROUTER_API_KEY = "sk-or-v1-본인키"
DATABASE_URL = "postgresql://..."

[auth]
redirect_uri = "https://자기앱이름.streamlit.app/oauth2callback"
cookie_secret = "아무 긴 문자열"
client_id = "..."
client_secret = "..."
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

### 배포 전 확인한 것

- `.env` 와 프록시가 없는 환경에서도 모듈이 모두 import 되고 앱이 죽지 않음
- 키가 없으면 화면에 오류를 띄우고 계속 돎
- `DATABASE_URL` 이 없으면 SQLite, 구글 설정이 없으면 버튼이 비활성
- `psycopg2-binary` 를 requirements 에 넣어 나중에 Supabase 로 바꿀 때 다시 배포하지 않아도 됨
