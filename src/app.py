"""냉장고 레시피 추천 — Streamlit 화면.

실행: streamlit run src/app.py

화면 구성
  사이드바 : app / 내 레시피 / 프로필, 로그인과 회원 가입
  본문     : ① 사진 업로드 ▸ ② 식재료 확인 ▸ ③ 레시피 추천

단계를 넘겨도 화면을 갈아 끼우지 않고 두 칸으로 나란히 둔다.
2단계는 사진과 재료를, 3단계는 재료와 레시피를 함께 보여 준다.
그래야 사진과 재료가, 재료와 레시피가 맞는지 한 화면에서 볼 수 있다 (노트 6.4.11.3목).
"""

import hashlib
import html

import auth
import client
import db
import recipe as recipe_mod
import streamlit as st
import vision

st.set_page_config(page_title="냉장고 레시피 추천", page_icon="🥬", layout="wide")

STEPS = ["사진 업로드", "식재료 확인", "레시피 추천"]

# 디자인 점검에서 고친 두 가지 (노트 6.4.10.4)
#  - 주요 버튼 빨강을 #D60000 으로. 흰 글자와의 명도 대비 5.44:1 (권장 4.5:1)
#  - 누르는 단추 높이를 44px 로. 권장 터치 크기
st.markdown("""
<style>
  div[data-testid="stHorizontalBlock"] { flex-wrap: nowrap; gap: .4rem; }
  div[data-testid="stHorizontalBlock"] > div { min-width: 0; }
  button[kind="primary"] { background-color: #D60000 !important; border-color: #D60000 !important;
                           color: #fff !important; }
  /* 마우스를 올리거나 누를 때도 같은 빨강 계열로. 기본값을 두면 버튼이 다른 색으로 깜빡인다 */
  button[kind="primary"]:hover:not(:disabled),
  button[kind="primary"]:focus:not(:active):not(:disabled) {
      background-color: #B30000 !important; border-color: #B30000 !important; color: #fff !important; }
  button[kind="primary"]:active:not(:disabled) {
      background-color: #960000 !important; border-color: #960000 !important; color: #fff !important; }
  .stButton button { min-height: 44px; }
  div[data-testid="stNumberInput"] button { min-height: 44px !important; }
  .chip { display: inline-block; background: #eee; color: #333; border-radius: 999px;
          padding: .25rem .75rem; margin: 0 .3rem .35rem 0; font-size: .85rem; }
  .steps { display: flex; gap: 3rem; flex-wrap: wrap; margin: .2rem 0 1rem; }
  .steps span { color: #888; }
  .steps span.on { color: #D60000; font-weight: 700; }
  .steps span.done { color: #333; }
</style>
""", unsafe_allow_html=True)


# ---------- 상태 ----------

@st.cache_resource(show_spinner=False)
def ready_db():
    """표 만들기는 한 번만 한다.

    `db.init()` 은 CREATE TABLE IF NOT EXISTS 세 번이라 연결을 3번 연다.
    리런마다 다시 하면 Supabase 에서는 리런마다 접속 3번이 된다.
    표는 한 번 만들면 그대로이므로 `st.cache_resource` 로 묶는다.
    """
    db.init()
    return True


def init_state():
    ready_db()
    defaults = {
        "user": None, "page": "app", "step": 1,
        "photo": None, "photo_view": None, "photo_name": "",
        "photo_bytes_before": 0, "photo_bytes_after": 0,
        "ingredients": [], "recipes": [],
        "vision_model": "", "recipe_model": "", "open_recipe": None,
        "saved_uids": set(),
        "log": [], "error": "", "auto_generate": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_flow():
    """처음부터 다시. 로그아웃할 때도 쓴다 (노트 6.4.9.1목 b.3)."""
    st.session_state.update(
        step=1, photo=None, photo_view=None, photo_name="",
        photo_bytes_before=0, photo_bytes_after=0,
        ingredients=[], recipes=[],
        vision_model="", recipe_model="", open_recipe=None,
        saved_uids=set(),
        log=[], error="", auto_generate=False,
    )


@st.cache_data(show_spinner=False)
def load_profile(user_id):
    """선호 조건 한 벌을 읽어 둔다.

    리런마다 다시 읽으면 재료 한 줄을 고칠 때마다 질의가 한 번씩 나간다.
    값으로 끝나는 것이라 `st.cache_data` 다. 저장한 뒤에는 `load_profile.clear()`.
    """
    return db.get_profile(user_id)


def profile():
    user = st.session_state.user
    return load_profile(user["id"]) if user else None


# ---------- 사이드바 ----------

def render_sidebar():
    with st.sidebar:
        for key, label in (("app", "app"), ("recipes", "내 레시피"), ("profile", "프로필")):
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                st.session_state.page = key
                st.rerun()
        st.divider()

        user = st.session_state.user
        if user:
            st.write(f"**{user['email']}**")
            if st.button("로그아웃", use_container_width=True):
                st.session_state.user = None
                reset_flow()
                st.rerun()
            return

        st.subheader("로그인 / 회원가입")
        if auth.google_ready():
            if st.button("Google로 로그인", use_container_width=True):
                st.login()
        else:
            st.button("Google로 로그인", use_container_width=True, disabled=True,
                      help="구글 로그인 설정(.streamlit/secrets.toml 의 [auth])이 없습니다.")
        st.divider()

        login_tab, signup_tab = st.tabs(["로그인", "회원가입"])
        with login_tab:
            email = st.text_input("이메일", key="li_email")
            password = st.text_input("비밀번호", type="password", key="li_pw")
            if st.button("로그인", key="li_go", use_container_width=True):
                try:
                    st.session_state.user = auth.log_in(email, password)
                    st.rerun()
                except auth.AuthError as error:
                    st.error(str(error))
        with signup_tab:
            email = st.text_input("이메일", key="su_email")
            password = st.text_input("비밀번호 (8자 이상)", type="password", key="su_pw")
            if st.button("회원가입", key="su_go", use_container_width=True):
                try:
                    st.session_state.user = auth.sign_up(email, password)
                    st.rerun()
                except auth.AuthError as error:
                    st.error(str(error))


# ---------- 공통 조각 ----------

def render_steps():
    """지난 단계에는 ✅ 를, 지금 단계에는 색을 준다."""
    marks = []
    for index, name in enumerate(STEPS, start=1):
        circle = "①②③"[index - 1]
        if index < st.session_state.step:
            marks.append(f'<span class="done">✅ {circle} {name}</span>')
        elif index == st.session_state.step:
            marks.append(f'<span class="on">{circle} {name}</span>')
        else:
            marks.append(f"<span>{circle} {name}</span>")
    st.markdown(f'<div class="steps">{"".join(marks)}</div>', unsafe_allow_html=True)


def chips(names):
    # 이름은 모델이 돌려준 값이거나 사용자가 직접 친 값이다. `<` 나 `&` 가 들어와도
    # 칩 배치가 깨지지 않게 글자 그대로 보이도록 바꿔 둔다.
    st.markdown("".join(f'<span class="chip">{html.escape(str(n))}</span>' for n in names),
                unsafe_allow_html=True)


def show_photo_size():
    """줄이기 전후 용량을 사진 아래에 남겨 둔다 (PRD 1단계 F2).

    진행 기록은 성공하면 사라지므로, 결과를 본 뒤에도 보이도록 따로 적는다.
    """
    before = st.session_state.photo_bytes_before
    after = st.session_state.photo_bytes_after
    if not before:
        return
    if not after:
        st.caption(f"올린 사진 {before / 1024:,.0f}KB (줄이기 전 크기입니다)")
        return
    st.caption(f"사진 용량 {before / 1024:,.0f}KB → {after / 1024:,.0f}KB 로 줄여서 보냅니다 "
               f"(긴 변 {vision.MAX_EDGE}px, JPEG 품질 {vision.JPEG_QUALITY})")


def show_error():
    if st.session_state.error:
        st.error(st.session_state.error)
        if st.session_state.log:
            with st.expander("진행 기록 보기"):
                st.code("\n".join(st.session_state.log))


# ---------- 각 칸 ----------

def panel_photo():
    st.subheader("① 사진 업로드")
    if st.session_state.photo is None:
        st.write("냉장고 사진을 업로드하거나, 이 영역으로 파일을 끌어다 놓으세요")
        uploaded = st.file_uploader("냉장고 사진", type=["jpg", "jpeg", "png"],
                                    label_visibility="collapsed")
        if uploaded is not None:
            data = uploaded.getvalue()
            st.session_state.photo = data
            st.session_state.photo_name = uploaded.name
            # 화면에 보일 작은 사진을 올릴 때 한 번만 만들어 둔다. 휴대전화 사진
            # 원본(수 MB)을 리런마다 st.image 로 넘기면 리런 1회가 85ms 씩 길어진다.
            # 모델에 보내는 것도 같은 크기라 보이는 것과 보내는 것이 맞아진다.
            try:
                view, _, _, before, after = vision.resize_image(data)
                st.session_state.photo_view = view
                st.session_state.photo_bytes_before = before
                st.session_state.photo_bytes_after = after
            except Exception:
                st.session_state.photo_view = None  # 열지 못하면 원본을 그대로 보여 준다
                st.session_state.photo_bytes_before = len(data)
                st.session_state.photo_bytes_after = 0
            st.rerun()
        return

    st.image(st.session_state.photo_view or st.session_state.photo,
             caption=st.session_state.photo_name, use_container_width=True)
    show_photo_size()
    if st.session_state.vision_model:
        st.caption(f"실제 응답 모델: `{st.session_state.vision_model}`")
    if not st.session_state.ingredients:
        if st.button("식재료 인식하기", type="primary", use_container_width=True):
            run_recognition(st.session_state.photo)
            st.rerun()


def panel_ingredients(show_next=True):
    st.subheader("② 식재료 확인")
    items = st.session_state.ingredients
    if not items:
        st.info("왼쪽에서 사진을 올리고 `식재료 인식하기` 를 누르세요.")
        return

    st.warning("AI 인식 결과는 부정확할 수 있습니다. "
               "이름/수량/단위를 확인하고 필요하면 직접 수정해주세요.")

    remove_id = None
    for item in items:
        # 위젯 key 에 순번이 아니라 고유 id 를 쓴다 (노트 6.4.11.4목).
        uid = item["_id"]
        name_col, qty_col, unit_col, del_col = st.columns([5, 4, 3, 2])
        item["name"] = name_col.text_input(
            "이름", item["name"], key=f"n_{uid}", label_visibility="collapsed")
        item["quantity"] = qty_col.number_input(
            "수량", 1, 999, int(item["quantity"]), key=f"q_{uid}",
            label_visibility="collapsed")
        item["unit"] = unit_col.selectbox(
            "단위", vision.UNITS, vision.UNITS.index(item["unit"]),
            key=f"u_{uid}", label_visibility="collapsed")
        if del_col.button("삭제", key=f"d_{uid}", use_container_width=True):
            remove_id = uid

    if remove_id is not None:
        st.session_state.ingredients = [i for i in items if i["_id"] != remove_id]
        st.session_state.recipes = []
        st.session_state.open_recipe = None
        st.rerun()

    # 맨 아래 한 줄로 직접 더하기
    with st.container(border=True):
        name_col, qty_col, unit_col, add_col = st.columns([5, 4, 3, 2])
        new_name = name_col.text_input("재료 이름", key="add_name",
                                       placeholder="재료 이름", label_visibility="collapsed")
        new_qty = qty_col.number_input("수량", 1, 999, 1, key="add_qty",
                                       label_visibility="collapsed")
        new_unit = unit_col.selectbox("단위", vision.UNITS, 0, key="add_unit",
                                      label_visibility="collapsed")
        if add_col.button("추가", key="add_go", use_container_width=True):
            if new_name.strip():
                items.append({"_id": f"manual-{len(items)}-{new_name}",
                              "name": new_name.strip(), "quantity": int(new_qty),
                              "unit": new_unit, "category": "기타"})
                st.rerun()

    if show_next and st.button("레시피 추천받기", type="primary", use_container_width=True):
        st.session_state.step = 3
        st.session_state.auto_generate = True  # 3단계에서 버튼을 다시 누르지 않아도 되게
        st.rerun()


def panel_recipes():
    st.subheader("③ 레시피 추천")
    items = [i for i in st.session_state.ingredients if i["name"].strip()]
    if not items:
        st.info("왼쪽에서 재료를 먼저 확인하세요.")
        return

    chips([i["name"] for i in items])

    saved = profile() or {}
    cuisine_col, level_col, time_col, serving_col = st.columns(4)
    cuisine = cuisine_col.selectbox("요리 종류", recipe_mod.CUISINE_OPTIONS,
                                    _index(recipe_mod.CUISINE_OPTIONS, saved.get("cuisine")))
    difficulty = level_col.selectbox("난이도", recipe_mod.DIFFICULTY_OPTIONS,
                                     _index(recipe_mod.DIFFICULTY_OPTIONS,
                                            saved.get("difficulty")))
    time_limit = time_col.selectbox("조리 시간", recipe_mod.TIME_OPTIONS,
                                    _index(recipe_mod.TIME_OPTIONS, saved.get("time_limit")))
    servings = serving_col.selectbox(
        "인원", recipe_mod.SERVING_OPTIONS,
        _index(recipe_mod.SERVING_OPTIONS, saved.get("servings")),
        format_func=lambda v: v if v == recipe_mod.ANY else f"{v}인분")

    label = "다시 추천받기" if st.session_state.recipes else "레시피 생성하기"
    if st.button(label, type="primary") or st.session_state.auto_generate:
        st.session_state.auto_generate = False
        run_generation(items, cuisine, difficulty, time_limit, servings)
        st.rerun()

    if st.session_state.recipe_model:
        st.caption(f"실제 응답 모델: `{st.session_state.recipe_model}`")
    show_error()

    if st.session_state.recipes:
        st.caption("💡 매 요청마다 다른 레시피가 나올 수 있어요. "
                   "마음에 안 들면 다시 추천받아보세요.")
        render_recipe_cards()


def _index(options, value):
    try:
        return options.index(value)
    except (ValueError, TypeError):
        return 0


# ---------- 모델 부르기 ----------

def failure_text(action, error):
    """모델 호출 실패를 사람이 읽을 한 줄로 바꾼다.

    status 0 은 키가 없을 때다. 이때는 `HTTP 0 오류.` 대신 무엇을 하면 되는지
    알려 주는 client 쪽 안내 문장을 그대로 쓴다.
    """
    if error.status == 0 and error.message:
        return error.message
    detail = error.message if error.status == 200 else client.explain(error.status)
    return f"{action} 실패 — {detail}"


def run_recognition(image_bytes):
    st.session_state.error = ""
    st.session_state.recipes = []
    st.session_state.ingredients = []
    st.session_state.open_recipe = None
    # 실패했을 때 지난번에 성공한 모델 이름이 남아 이번 결과처럼 보이면 안 된다
    # (PRD 1단계 F6).
    st.session_state.vision_model = ""
    st.session_state.recipe_model = ""
    lines = []
    box = st.empty()

    def on_event(text):
        lines.append(text)
        box.code("\n".join(lines[-8:]))

    try:
        with st.spinner("인식하는 중입니다. 막히면 예비 모델로 넘어갑니다."):
            key = client.get_api_key()
            picked = (profile() or {}).get("vision_models") or None
            result = vision.recognize(image_bytes, key, models=picked, on_event=on_event)
    except client.ModelError as error:
        st.session_state.error = failure_text("식재료 인식", error)
        st.session_state.log = lines
    except Exception as error:
        st.session_state.error = f"식재료 인식 실패 — {error}"
        st.session_state.log = lines
    else:
        st.session_state.ingredients = result["ingredients"]
        st.session_state.vision_model = result["model"]
        st.session_state.log = result["log"]
        # 줄이기 전후 용량을 화면에 남겨 둔다 (PRD 1단계 F2)
        st.session_state.photo_bytes_before = result["original_bytes"]
        st.session_state.photo_bytes_after = result["resized_bytes"]
        st.session_state.step = 2


def run_generation(items, cuisine, difficulty, time_limit, servings):
    st.session_state.error = ""
    st.session_state.recipes = []
    st.session_state.open_recipe = None
    # 실패하면 지난번 모델 이름도 같이 지운다 (PRD 1단계 F6).
    st.session_state.recipe_model = ""
    lines = []
    box = st.empty()

    def on_event(text):
        lines.append(text)
        box.code("\n".join(lines[-8:]))

    try:
        with st.spinner("레시피를 만드는 중입니다."):
            key = client.get_api_key()
            picked = (profile() or {}).get("text_models") or None
            result = recipe_mod.generate(items, cuisine, difficulty, time_limit, servings,
                                         key, models=picked, on_event=on_event)
    except client.ModelError as error:
        st.session_state.error = failure_text("레시피 추천", error)
        st.session_state.log = lines
    except Exception as error:
        st.session_state.error = f"레시피 추천 실패 — {error}"
        st.session_state.log = lines
    else:
        st.session_state.recipes = tag_recipes(result["recipes"])
        st.session_state.recipe_model = result["model"]
        st.session_state.log = result["log"]


# ---------- 레시피 카드와 상세 ----------

def tag_recipes(recipes):
    """레시피마다 고유 식별자를 붙인다. 위젯 key 와 저장 여부 표시에 쓴다.

    순번을 쓰면 다시 추천받아 차례가 바뀔 때 엉뚱한 카드가 저장된 것처럼 보인다.
    """
    used = set()
    for item in recipes:
        seed = item["title"] + "|" + "|".join(item["steps"])
        base = hashlib.md5(seed.encode("utf-8")).hexdigest()[:10]
        uid, suffix = base, 2
        while uid in used:  # 제목과 순서까지 같은 레시피가 둘 오면 뒤쪽에 번호를 붙인다
            uid = f"{base}-{suffix}"
            suffix += 1
        used.add(uid)
        item["_uid"] = uid
    return recipes


def save_button(item, place):
    """레시피 저장 버튼 (PRD 3단계 F3).

    이미 저장한 레시피는 눌리지 않게 막아 같은 레시피가 여러 벌 쌓이지 않게 한다.
    """
    uid = item.get("_uid") or item["title"]
    key = f"save_{place}_{uid}"
    if not st.session_state.user:
        st.button("저장", key=key, use_container_width=True, disabled=True,
                  help="로그인하면 레시피를 저장할 수 있습니다.")
        return
    if uid in st.session_state.saved_uids:
        st.button("저장됨", key=key, use_container_width=True, disabled=True,
                  help="이미 저장했습니다. 사이드바의 `내 레시피` 에서 볼 수 있습니다.")
        return
    if st.button("저장", key=key, use_container_width=True):
        db.save_recipe(st.session_state.user["id"],
                       {k: v for k, v in item.items() if not k.startswith("_")})
        st.session_state.saved_uids.add(uid)
        st.toast(f"{item['title']} 을(를) 저장했습니다. `내 레시피` 에서 볼 수 있습니다.")
        st.rerun()


def render_recipe_cards():
    recipes = st.session_state.recipes
    # 한 줄에 카드 3개까지만 둔다. 모델이 더 많이 돌려줘도 열이 좁아지지 않는다.
    for start in range(0, len(recipes), 3):
        chunk = recipes[start:start + 3]
        for offset, (column, item) in enumerate(zip(st.columns(len(chunk)), chunk)):
            number = start + offset
            with column.container(border=True):
                # 카드 윗부분의 높이를 고정해야 카드마다 버튼의 세로 위치가 같아진다.
                # 부족한 재료가 두 줄이면 그 카드만 버튼이 밀렸다 (노트 6.4.9.1목 b.2).
                with st.container(height=170, border=False):
                    st.markdown(f"**{item['title']}**")
                    st.caption(f"⏱ 약 {item['time_minutes']}분")
                    if item["missing_ingredients"]:
                        st.warning("부족: " + ", ".join(item["missing_ingredients"]))
                    else:
                        st.info("부족한 재료 없음")
                # 버튼은 카드마다 같은 차례로 세로로 쌓아 높이가 어긋나지 않게 한다.
                if st.button("자세히 보기", key=f"open_{item.get('_uid', number)}",
                             use_container_width=True):
                    st.session_state.open_recipe = number
                    st.rerun()
                save_button(item, "card")

    if not st.session_state.user:
        st.caption("로그인하면 마음에 든 레시피를 저장할 수 있습니다.")

    if st.session_state.open_recipe is not None:
        render_recipe_detail(recipes[st.session_state.open_recipe])


def render_recipe_detail(item):
    st.divider()
    title_col, back_col = st.columns([5, 2])
    title_col.markdown(f"### 📖 {item['title']}")
    if back_col.button("← 목록으로", use_container_width=True):
        st.session_state.open_recipe = None
        st.rerun()

    if item["used_ingredients"]:
        st.markdown("**사용 재료**: " + ", ".join(item["used_ingredients"]))
    if item["missing_ingredients"]:
        st.warning("**부족한 재료**: " + ", ".join(item["missing_ingredients"]))

    st.markdown("**조리 순서**")
    for number, step in enumerate(item["steps"], start=1):
        st.write(f"{number}. {step}")

    save_col, _rest = st.columns([2, 5])
    with save_col:
        save_button(item, "detail")
    if not st.session_state.user:
        st.caption("로그인하면 레시피를 저장할 수 있습니다.")


# ---------- 다른 쪽 화면 ----------

def page_saved():
    st.title("내 레시피")
    user = st.session_state.user
    if not user:
        st.info("로그인하면 저장한 레시피를 볼 수 있습니다.")
        return
    rows = db.list_recipes(user["id"])
    if not rows:
        st.info("아직 저장한 레시피가 없습니다.")
        return
    for row in rows:
        with st.expander(row["title"]):
            item = row["recipe"]
            st.caption(f"⏱ 약 {item['time_minutes']}분 · {item['servings']}인분")
            for number, step in enumerate(item["steps"], start=1):
                st.write(f"{number}. {step}")
            if st.button("삭제", key=f"rm_{row['id']}"):
                db.delete_recipe(row["id"], user["id"])
                st.rerun()


def page_profile():
    st.title("프로필")
    user = st.session_state.user
    if not user:
        st.info("로그인하면 선호 조건을 저장할 수 있습니다.")
        return
    saved = load_profile(user["id"])

    st.subheader("선호 조건")
    cuisine_col, level_col, time_col, serving_col = st.columns(4)
    cuisine = cuisine_col.selectbox("요리 종류", recipe_mod.CUISINE_OPTIONS,
                                    _index(recipe_mod.CUISINE_OPTIONS, saved["cuisine"]))
    difficulty = level_col.selectbox("난이도", recipe_mod.DIFFICULTY_OPTIONS,
                                     _index(recipe_mod.DIFFICULTY_OPTIONS, saved["difficulty"]))
    time_limit = time_col.selectbox("조리 시간", recipe_mod.TIME_OPTIONS,
                                    _index(recipe_mod.TIME_OPTIONS, saved["time_limit"]))
    servings = serving_col.selectbox(
        "인원", recipe_mod.SERVING_OPTIONS,
        _index(recipe_mod.SERVING_OPTIONS, saved["servings"]),
        format_func=lambda v: v if v == recipe_mod.ANY else f"{v}인분")

    st.subheader("AI 모델 선택")
    st.caption("고르지 않으면 기본 차례를 그대로 씁니다.")
    vision_col, text_col = st.columns(2)
    vision_models = vision_col.multiselect("식재료 인식 모델", vision.VISION_MODELS,
                                           saved["vision_models"])
    text_models = text_col.multiselect("레시피 생성 모델", recipe_mod.TEXT_MODELS,
                                       saved["text_models"])

    if st.button("저장", type="primary"):
        db.save_profile(user["id"], cuisine, difficulty, time_limit, servings,
                        vision_models, text_models)
        load_profile.clear()  # 읽어 둔 옛 값을 버린다
        st.success("저장했습니다.")


# ---------- 들어가는 곳 ----------

def render_app():
    title_col, reset_col = st.columns([5, 1])
    title_col.title("🥬 냉장고 레시피 추천")
    if reset_col.button("🔄 처음부터", use_container_width=True):
        reset_flow()
        st.rerun()

    render_steps()
    st.divider()

    step = st.session_state.step
    if step == 1:
        panel_photo()
        show_error()
    elif step == 2:
        # 사진과 재료를 한 화면에서 맞춰 본다.
        left, right = st.columns(2)
        with left:
            panel_photo()
        with right:
            show_error()
            panel_ingredients()
    else:
        # 재료와 레시피를 한 화면에서 맞춰 본다.
        left, right = st.columns(2)
        with left:
            panel_ingredients(show_next=False)
            if st.button("← 이전 (식재료 다시 확인)", use_container_width=True):
                st.session_state.step = 2
                st.rerun()
        with right:
            panel_recipes()


def main():
    init_state()
    render_sidebar()
    page = st.session_state.page
    if page == "recipes":
        page_saved()
    elif page == "profile":
        page_profile()
    else:
        render_app()


if __name__ == "__main__":
    main()
