# PRD 3단계 — 프로필과 레시피 저장

## 목표

회원이 자기 프로필과 마음에 든 레시피를 저장하고 다시 볼 수 있게 한다.
AI 모델은 쓰지 않는다.

## 저장소

- DB: Supabase (Postgres). 연결 문자열은 `.env` 의 `DATABASE_URL`
- 연결 문자열이 없으면 내 PC 의 SQLite 로 떨어진다 (혼자 시험할 때)

SQLite 로 배포하면 앱을 다시 띄울 때 데이터가 사라진다. 배포용은 Supabase 를 쓴다.

## 로그인

- 아이디와 비밀번호
- 구글 로그인 (`st.login`)

구글 값은 `.streamlit/secrets.toml` 의 `[auth]` 블록에 둔다. 저장소에 올리지 않는다.

## 표

### users

| 칸 | 형 | 설명 |
| --- | --- | --- |
| id | serial | 기본키 |
| email | text | 고유 |
| password_hash | text | 구글 로그인이면 빈 값 |
| auth_provider | text | `local` 또는 `google` |
| created_at | timestamp | |

비밀번호는 해시로만 저장한다. 원문을 두지 않는다.

### profiles

| 칸 | 형 | 설명 |
| --- | --- | --- |
| user_id | int | users 참조 |
| cuisine | text | 기본 요리 종류 |
| difficulty | text | 기본 난이도 |
| time_limit | text | 기본 조리 시간 |
| servings | int | 기본 인원 |

### saved_recipes

| 칸 | 형 | 설명 |
| --- | --- | --- |
| id | serial | 기본키 |
| user_id | int | users 참조 |
| title | text | |
| payload | jsonb | 레시피 전체 |
| created_at | timestamp | |

## 기능

### F1. 회원 가입과 로그인

- 이메일 모양과 비밀번호 길이를 검사한다
- 로그아웃하면 재료와 레시피 등 진행 상태를 모두 지운다

로그아웃했는데 이전 화면이 남아 있으면 안 된다 (노트 6.4.9.1목 b.3).

### F2. 프로필

- 요리 종류, 난이도, 조리 시간, 인원을 저장한다
- 2단계 화면에서 이 값을 기본값으로 띄우되 고칠 수 있다

### F3. 레시피 저장

- 레시피 카드에 `저장` 버튼을 둔다
- `내 레시피` 화면에서 목록과 자세한 내용을 본다
- 저장한 레시피를 지울 수 있다

## 받아들이는 조건

- [ ] 가입과 로그인이 된다
- [ ] 구글 로그인이 된다
- [ ] 프로필 값이 2단계의 기본값으로 들어간다
- [ ] 저장한 레시피가 다시 로그인해도 남아 있다
- [ ] 앱을 다시 띄워도 Supabase 의 데이터는 남아 있다
- [ ] 로그아웃하면 이전 화면이 남지 않는다
