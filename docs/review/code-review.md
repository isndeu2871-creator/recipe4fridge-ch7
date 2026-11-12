# 코드 검토 보고서

- 검토일: 2026-11-12
- 대상 커밋: `eccb386` (main, 작업 폴더 깨끗한 상태)
- 검토 범위: `src/` 여섯 파일, `tests/` 네 파일, `test_openrouter.py`, `run_test.bat`,
  설정·문서(`.env.example`, `.gitignore`, `requirements.txt`, `requirements-dev.txt`,
  `.streamlit/config.toml`, `README.md`, `CLAUDE.md`), 기준 문서 `docs/PRD_step1~3.md`
- 열지 않은 파일: `.env`, `.streamlit/secrets.toml`
  (두 파일을 참조하는 코드만 읽고, 파일이 있을 때와 없을 때 양쪽을 판단했다)
- 고친 것: 없음. 이 문서는 보고까지다.

고쳐야 할 것 13건, 봐두면 좋을 것 7건. 아래 1~8번은 실제로 코드를 열어 확인했다.

---

## 바로 고쳐야 할 것 (앱이 죽거나 기능이 안 됨)

### 1. 구글 로그인이 끝까지 연결되지 않음

- 위치: `src/app.py:95`, `src/auth.py:64`
- 무엇이: `st.login()` 만 부르고, 로그인 뒤 `st.user` 를 읽어
  `auth.log_in_with_google()` 로 `session_state.user` 를 채우는 코드가 없다.
  저장소 전체 검색에서 `log_in_with_google` 은 `auth.py` 와 `tests/` 에만 나온다.
  로그아웃에서 `st.logout()` 도 부르지 않는다.
- 어떻게 터지나: `[auth]` 를 채워 배포한 뒤 `Google로 로그인` 을 눌러 구글 인증을
  마치고 돌아와도 `session_state.user` 가 계속 `None` 이다. 사이드바는 여전히 로그인
  폼을 보여 주고, 레시피 저장과 프로필을 쓸 수 없다.
- 근거: `docs/PRD_step3.md` 로그인, 받아들이는 조건
- 손볼 방향: `main()` 앞쪽에서 `st.user.is_logged_in` 이고 `session_state.user` 가
  비었으면 `auth.log_in_with_google(st.user.email)` 로 채운다. 로그아웃에서는 구글
  사용자일 때 `st.logout()` 도 부른다.

### 2. 수량이 999 를 넘으면 2단계 화면이 예외로 바뀜

- 위치: `src/app.py:192`, 원인은 `src/vision.py:89`
- 무엇이: `number_input("수량", 1, 999, ...)` 인데 `vision.normalize` 는
  `quantity = max(1, quantity)` 로 아래쪽만 막고 상한이 없다.
- 어떻게 터지나: 모델이 `{"name":"우유","quantity":1000,"unit":"ml"}` 이나 1500g 을
  돌려주면 값이 max 를 넘어 `StreamlitValueAboveMaxError` 로 2단계 화면 전체가 예외
  화면이 된다. 단위에 g 와 ml 이 있어 충분히 나올 값이다. 같은 이름·단위를 합치는
  코드(`vision.py:99` 의 `seen[key]["quantity"] += quantity`)도 합계가 999 를 넘길 수 있다.
- 근거: 일반 버그(범위 밖 값), `docs/PRD_step1.md` F5
- 손볼 방향: `normalize` 에서 `min(999, ...)` 로 자르거나 `number_input` 의
  `max_value` 를 크게 잡는다.

### 3. 직접 더한 재료 `_id` 가 겹쳐 앱이 죽음

- 위치: `src/app.py:218`
- 무엇이: 수동 추가 재료의 `_id` 를 `f"manual-{len(items)}-{new_name}"` 으로 만든다.
  항목을 지우면 `len(items)` 가 줄어 같은 id 가 다시 만들어진다.
- 어떻게 터지나: 인식된 재료 3개에서 "x" 를 추가하면 `manual-3-x` 가 된다(len=3).
  아무 재료나 하나 지우면 len 이 3으로 돌아오고, 다시 "x" 를 추가하면 `manual-3-x` 가
  또 생겨 `key=n_manual-3-x` 가 중복되어 `DuplicateWidgetID` 로 죽는다.
- 근거: `CLAUDE.md` "재료 줄의 위젯 key 에는 `_id`" — key 를 `_id` 로 쓰는 규칙은
  지켰지만 `_id` 자체가 고유하지 않다(노트 6.4.11.4목의 취지).
- 손볼 방향: `uuid.uuid4().hex` 나 `session_state` 에 둔 단조 증가 카운터를 쓴다.

### 4. 프로필 인원을 `상관없음` 으로 저장하면 ValueError

- 위치: `src/app.py:425`, `src/db.py:130`
- 무엇이: `recipe.py:12` 의 `ANY = "상관없음"` 이 `SERVING_OPTIONS = [ANY, 1, 2, 3, 4]`
  첫 자리에 있는데, `save_profile` 이 `int(servings)` 를 부른다. 컬럼도 INTEGER(`db.py:88`)다.
- 어떻게 터지나: 로그인한 뒤 프로필에서 인원을 `상관없음` 으로 두고 `저장` 을 누르면
  `ValueError: invalid literal for int()` 가 난다. 같이 고른 다른 조건도 저장되지 않는다.
- 근거: 일반 버그(처리되지 않는 예외), `docs/PRD_step3.md` F2
- 손볼 방향: `상관없음` 이면 `None`(NULL)로 저장하고 읽을 때 되돌린다. 또는 프로필
  화면의 인원 선택지에서 `상관없음` 을 뺀다.

### 5. 네트워크 예외 한 번으로 예비 모델 전환이 통째로 멈춤

- 위치: `src/client.py:88`(`requests.post`), `src/client.py:100`(`response.json()`)
- 무엇이: `call_once` 가 Timeout·ConnectionError 와 JSON 파싱 오류를 `ModelError` 로
  감싸지 않고 그대로 올려 보낸다. `call_with_fallback` 은 `ModelError` 만 잡는다.
- 어떻게 터지나: 선정 모델이 120초 타임아웃에 걸리거나 200 이면서 본문이 JSON 이
  아니면, 예비 모델을 **하나도** 시도하지 않고 전체 호출이 끝난다. 앱은
  `except Exception` 으로 받아 "식재료 인식 실패 — HTTPSConnectionPool..." 원문을 보여 준다.
- 근거: `docs/PRD_step1.md` F4 "막히면 예비 모델로", 일반 버그(네트워크·JSON 경로)
- 손볼 방향: `call_once` 안에서 `requests.RequestException` 과 `ValueError` 를
  `ModelError(0, ...)` 로 바꿔 던진다. 타임아웃은 재시도 없이 다음 모델로 넘긴다.

---

## 그다음

### 6. 키가 없을 때의 안내 문구가 "HTTP 0 오류." 로 바뀜

- 위치: `src/client.py:63`, `src/app.py:294`, `src/app.py:325`
- 무엇이: `get_api_key()` 는 `ModelError(0, "OPENROUTER_API_KEY 를 찾지 못했습니다...")` 를
  던지는데, 앱은 `error.message if error.status == 200 else client.explain(error.status)`
  라서 `message` 를 버린다.
- 어떻게 터지나: `.env` 도 Secrets 도 없는 상태(배포 직후 Secrets 를 안 넣은 경우)에서
  인식 버튼을 누르면 "식재료 인식 실패 — HTTP 0 오류." 만 나온다. 학생이 무엇을 고쳐야
  하는지 알 수 없다. 앱이 죽지는 않으므로 안내가 가려지는 문제다.
- 손볼 방향: `status == 0` 일 때는 `error.message` 를 그대로 보여 주거나 `explain` 에
  0 번 항목을 둔다.

### 7. 실패했을 때 이전에 성공한 모델 표시가 남음

- 위치: `src/app.py:277`(`run_recognition`), `src/app.py:308`(`run_generation`)
- 무엇이: 시작할 때 `error`·`recipes`·`ingredients`·`open_recipe` 는 비우지만
  `vision_model`·`recipe_model` 은 비우지 않는다.
- 어떻게 터지나: 한 번 성공한 뒤 `다시 추천받기` 가 실패하면 실패 문구 바로 위에
  "실제 응답 모델: <이전에 성공한 모델>" 이 그대로 남아 이번 결과처럼 읽힌다.
- 근거: `docs/PRD_step1.md` F6 "성공한 옛 결과가 남아 이번 사진의 결과처럼 보이면 안 된다"
- 손볼 방향: 두 함수 시작부에서 `vision_model`·`recipe_model` 도 빈 문자열로 둔다.

### 8. 사진 줄이기 전후 용량이 화면에 남지 않음

- 위치: `src/vision.py:116`, `src/app.py:301`
- 무엇이: 줄이기 전후 KB 는 `on_event` 로 `st.empty()` 칸에 잠깐 찍힐 뿐이다. 성공하면
  `st.rerun()` 으로 사라지고 `result["log"]` 에도 들어 있지 않다(`call_with_fallback` 의
  log 만 담긴다). `original_bytes`·`resized_bytes` 는 `app.py` 에서 쓰이지 않는다.
- 어떻게 터지나: 성공한 뒤에는 용량 정보를 볼 수 없어 PRD 의 "줄이기 전후 용량을 화면에
  보여 준다" 가 지켜지지 않는다.
- 근거: `docs/PRD_step1.md` F2
- 손볼 방향: 성공 시 두 값을 `session_state` 에 저장해 사진 아래 `st.caption` 으로 보여 준다.

### 9. 재료 이름이 HTML 로 그대로 삽입됨

- 위치: `src/app.py:139`
- 무엇이: `chips()` 가 `f'<span class="chip">{n}</span>'` 를 `unsafe_allow_html=True` 로
  넣는다. 이름은 모델 출력이거나 사용자가 직접 친 값이다.
- 어떻게 터지나: 이름에 `<`, `&`, 태그가 들어가면 칩 배치가 깨진다. 사진 속 글자가
  이름이 되는 프롬프트 주입 경로도 있다.
- 손볼 방향: `html.escape(n)` 을 쓴다.

### 10. `st.login` 에 필요한 패키지와 버전이 requirements 에 없음

- 위치: `requirements.txt:1`
- 무엇이: `streamlit>=1.40` 인데 `st.login` 은 1.42 부터 있고 Authlib 가 필요하다.
  Authlib 는 requirements 에 없다.
- 어떻게 터지나: `[auth]` 를 채워도 1.40/1.41 이 깔리면 `st.login` 이 AttributeError 를
  내고, Authlib 가 없으면 로그인 클릭 시 설치하라는 오류가 난다. 구글 로그인을 켜는
  순간에야 드러난다.
- 손볼 방향: `streamlit>=1.42`, `Authlib>=1.3.2` 로 올린다.

### 11. DB 표가 PRD 와 다름

- 위치: `src/db.py:75`~`src/db.py:97`
- 무엇이: `docs/PRD_step3.md` 는 users·saved_recipes 에 `created_at`, saved_recipes.payload
  는 `jsonb` 라고 한다. 코드에는 `created_at` 이 없고 payload 는 TEXT 다. profiles 에는
  PRD 에 없는 `vision_models`·`text_models` 칸이 있다(기능상 필요해 보이나 문서에 없음).
- 어떻게 터지나: 당장 죽지는 않는다. 저장 목록의 최신순 기준이 id 뿐이고 저장 시각을
  알 수 없다. Supabase 에서 `jsonb` 로 조회·검색하려면 막힌다.
- 손볼 방향: PRD 를 코드에 맞게 고치거나 `created_at` 을 추가한다.

### 12. `test_openrouter.py` 가 빈 `choices` 에 죽고 규칙과도 어긋남

- 위치: `test_openrouter.py:100`, `test_openrouter.py:122`, `test_openrouter.py:204`
- 무엇이: 두 가지다.
  - (a) `response.json()["choices"][0]["message"]["content"]` 를 방어 없이 읽는다.
    200 인데 `choices` 가 비면 KeyError/IndexError, content 가 None 이면 이후
    `answer.strip()` 이 AttributeError 다. `main()` 은 `RequestException` 만 잡으므로
    학생 PC 에서 트레이스백으로 끝난다(노트 6.4.5.3목 c.2 의 바로 그 오류).
  - (b) 예비로 넘어가는 조건이 404/429 뿐이라 500/503 이면 바로 `raise` 한다.
    `max_tokens` 를 주지 않아 추론 모델이 예비에 걸리면 빈 답이 올 수 있다.
- 근거: `CLAUDE.md` 모델 호출 규칙(HTTP 200 + 빈 `choices`, `max_tokens` 1500 이상)
- 손볼 방향: 최소한 `.get("choices")` 를 확인해 비면 예비로 넘기고 `max_tokens` 를
  1500 이상 준다. 수동 시험 스크립트라도 `client.call_with_fallback` 으로 갈아타는 쪽이
  낫다(`src` 를 `sys.path` 에 넣으면 된다).

### 13. `python3` 가 먼저 나오는 안내

- 위치: `test_openrouter.py:3`("실행: python3 test_openrouter.py"),
  `test_openrouter.py:171`("python3 -m pip install pillow"), `CLAUDE.md` 명령 블록
- 무엇이: 학생은 윈도를 쓰므로 `python` 쪽이 먼저 와야 한다. `README.md` 3절은 윈도가
  먼저라 맞다.
- 근거: `CLAUDE.md` "명령을 안내할 때 윈도 쪽을 먼저 적는다"
- 손볼 방향: `python test_openrouter.py` 를 먼저 적고 맥·리눅스를 뒤에 붙인다.

---

## 봐두면 좋을 것 (확실하지 않거나 급하지 않음)

- **시작 때 DB 가 죽으면 앱 전체가 죽음**: `init_state()` 가 매 리런마다 `db.init()` 을
  부른다(`src/app.py:48`). `DATABASE_URL` 이 있는데 Supabase 접속이 안 되면
  `psycopg2.OperationalError` 가 잡히지 않아 로그인과 사진 화면까지 막힌다. 설정이 아예
  없을 때는 SQLite 로 떨어져 문제없다. 리런마다 `init()` 이 연결 3번, `profile()` 이
  1번씩 열어 Supabase 에서는 느리다. `st.cache_resource` 로 한 번만 하게 할 수 있다.
- **프로필 `multiselect` 기본값**: `saved["vision_models"]` 에 저장된 모델이 나중에
  `VISION_MODELS` 목록에서 빠지면 StreamlitAPIException 이 날 수 있다(`src/app.py:433`).
  목록을 바꿀 때만 문제다.
- **레시피 개수**: `recipe.normalize` 가 3개로 자르지 않는다. 모델이 5개를 주면 카드 열이
  5개가 되어 폭 375px 에서 더 좁아진다. `parse_json` 이 배열을 돌려주면 `data.get` 이
  AttributeError 를 내고 앱은 그 원문을 화면에 보여 준다(죽지는 않음).
- **저장 버튼 위치**: `docs/PRD_step3.md` F3 은 "레시피 카드에 `저장` 버튼" 이라는데
  코드는 상세 칸에만 `레시피 저장` 이 있다(`src/app.py:379`). 같은 레시피를 누를 때마다
  중복 저장된다.
- **구글 계정 연결**: `log_in_with_google` 은 같은 이메일의 `local` 계정이 있으면 그
  계정으로 들여보낸다(`src/auth.py:69`). 가입 때 이메일 확인이 없어, 남의 이메일로 미리
  가입해 둔 사람이 그 계정의 비밀번호를 아는 상태가 된다. 수업용이면 넘어가도 된다.
- **가입 경쟁**: `sign_up` 이 `find_user` 후 `INSERT` 라서 동시 가입 때 UNIQUE 위반이
  잡히지 않는다.
- **키 일부 출력**: `test_openrouter.py:57` 이 키의 앞 10자와 뒤 4자를 콘솔에 찍는다.
  파일에는 남지 않지만 화면 공유 때 노출된다.
- **문서와 코드 불일치**: `README.md:303` 은 카드 윗부분 높이를 "210px" 라 하는데 코드는
  `height=170`(`src/app.py:346`)이다. README 7절 폴더 표에 `recipe.py`·`db.py`·`auth.py`
  가 빠져 있다. `.env.example` 의 `OPENROUTER_TEXT_MODEL`·`OPENROUTER_VISION_MODEL` 은
  코드에서 읽지 않는다(네 곳 값 일치 점검용으로는 의미가 있다). `DATABASE_URL` 견본이 없다.
- **버튼 색**: `button[kind="primary"]` 로 빨강을 덮지만 hover 색은 Streamlit 기본
  그대로다. `.streamlit/config.toml` 에 `[theme] primaryColor = "#D60000"` 을 두는 방법도 있다.

---

## 확인한 것 (제대로 지켜져 있음)

1. **모델 이름 네 곳이 같은 값**
   - 텍스트 1번: `src/recipe.py:6`, `test_openrouter.py:20`, `.env.example:5`,
     `README.md`(36·215행) 모두 `nvidia/nemotron-3-super-120b-a12b:free`
   - 멀티모달 1번: `src/vision.py:14`, `test_openrouter.py:26`, `.env.example:8`,
     `README.md`(35·219행) 모두 `google/gemma-4-26b-a4b-it:free`
   - 예비 목록도 PRD·`src`·`test_openrouter.py` 가 서로 같다.
2. **예비 제공 업체가 섞여 있음**: 텍스트는 nvidia, minimax, openrouter, cohere.
   이미지는 google, minimax, nvidia, dots-studio. 각 목록 안에서 업체가 겹치지 않는다.
3. **`max_tokens` 가 전부 1500 이상**: `src/client.py:79`·`:111` 기본 2000,
   `src/client.py:145` 는 빈 답이면 4배, `src/vision.py:124` 와 `src/recipe.py:91` 은 4000.
   (`test_openrouter.py` 는 아예 주지 않는다 — 위 12번)
4. **`call_with_fallback` 의 네 경로가 다 있음**: 빈 `choices` → `ModelError(200)`
   (`client.py:101`), 빈 본문 → 같은 모델에 토큰 4배로 한 번만(`:143`),
   429/500/503 → `RETRY_DELAYS=(10,20)` 로 3차까지(`:150`), 404 등 → 재시도 없이 다음 모델.
   `tests/test_client.py` 가 이를 시험한다(500/503 만 직접 시험이 없다).
5. **순수 모듈**: `import streamlit` 은 `client.get_api_key` 안(`client.py:54`)과
   `db.py`·`auth.py` 의 함수 안뿐이다. `client.py`·`vision.py` 모듈 맨 위에는 없다.
6. **화면 규칙**: 재료 줄 위젯 key 는 `n_{uid}`·`q_{uid}`·`u_{uid}`·`d_{uid}` 로 `_id`
   기반이고 지울 때도 `_id` 로 걸러 낸다(3번의 id 충돌은 별개). 레시피 카드 윗부분은
   `st.container(height=170)` 으로 고정. 로그아웃(`app.py:86`)과 `처음부터`(`:449`)가
   모두 `reset_flow()` 를 쓴다. 주요 버튼 색은 `#D60000`(`app.py:32`)이고 단추 최소 높이
   44px 도 있다.
7. **외부 설정이 없을 때**: `DATABASE_URL` 이 없으면 SQLite(`data/app.db`)로 떨어진다.
   `[auth]` 가 없으면 `google_ready()` 가 False 라 `Google로 로그인` 이 `disabled` 다.
   `get_api_key` 도 `st.secrets` 부재를 삼켜서, `.env` 와 Secrets 가 모두 없어도 import 와
   화면은 죽지 않는다(6번의 문구 문제는 별개).
8. **`tests/` 가 네트워크를 쓰지 않음**: `requests.post` 를 `monkeypatch` 로 바꾸고
   `time.sleep` 도 막았으며 `call_with_fallback` 도 가짜로 바꾼다. db 시험은 `tmp_path` 의
   SQLite 만 쓴다.
9. **키 값이 어디에도 없음**: `.env.example` 은 자리표시자
   (`sk-or-v1-여기에_발급받은_키를_붙여넣기`)뿐이고 `README.md`·`run_test.bat` 도 자리표시자다.
10. **`.gitignore`**: `.env`, `.env.*`, `!.env.example`, `.streamlit/secrets.toml`, `data/`
    가 모두 막혀 있다.
11. **`.env` 파싱**: `load_env()` 가 외부 패키지 없이 직접 파싱한다. python-dotenv 의존이
    없다. `test_openrouter.py` 도 키가 없으면 안내 후 `sys.exit(1)` 이다.
12. **SQL**: 전부 `?` 파라미터 바인딩이고 이어 붙인 값이 없다. 연결은 `finally` 에서 닫고
    커밋도 한다. `delete_recipe` 는 `user_id` 조건이 있고 시험으로 확인된다. 비밀번호는
    솔트가 있는 PBKDF2 해시로만 저장된다.
13. **`run_test.bat`**: 윈도용(`python`, `cd /d`, 안내 문구)이 맞고 `README.md` 3절도
    윈도가 먼저다.
