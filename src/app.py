"""냉장고 레시피 추천 — Streamlit 화면.

실행: streamlit run src/app.py

화면 구성
  사이드바 : app / 내 레시피 / 프로필, 로그인과 회원 가입
  본문     : ① 사진 업로드 ▸ ② 식재료 확인 ▸ ③ 레시피 추천

단계를 넘겨도 화면을 갈아 끼우지 않고 두 칸으로 나란히 둔다.
2단계는 사진과 재료를, 3단계는 재료와 레시피를 함께 보여 준다.
그래야 사진과 재료가, 재료와 레시피가 맞는지 한 화면에서 볼 수 있다 (노트 6.4.11.3목).
"""

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
  button[kind="primary"] { background-color: #D60000 !important; border-color: #D60000 !important; }
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

def init_state():
    db.init()
    defaults = {
        "user": None, "page": "app", "step": 1,
        "photo": None, "photo_name": "", "ingredients": [], "recipes": [],
        "vision_model": "", "recipe_model": "", "open_recipe": None,
        "log": [], "error": "", "auto_generate": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_flow():
    """처음부터 다시. 로그아웃할 때도 쓴다 (노트 6.4.9.1목 b.3)."""
    st.session_state.update(
        step=1, photo=None, photo_name="", ingredients=[], recipes=[],
        vision_model="", recipe_model="", open_recipe=None,
        log=[], error="", auto_generate=False,
    )


def profile():
    user = st.session_state.user
    return db.get_profile(user["id"]) if user else None


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
    st.markdown("".join(f'<span class="chip">{n}</span>' for n in names),
                unsafe_allow_html=True)


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
            st.session_state.photo = uploaded.getvalue()
            st.session_state.photo_name = uploaded.name
            st.rerun()
        return

    st.image(st.session_state.photo, caption=st.session_state.photo_name,
             use_container_width=True)
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

def run_recognition(image_bytes):
    st.session_state.error = ""
    st.session_state.recipes = []
    st.session_state.ingredients = []
    st.session_state.open_recipe = None
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
        detail = error.message if error.status == 200 else client.explain(error.status)
        st.session_state.error = f"식재료 인식 실패 — {detail}"
        st.session_state.log = lines
    except Exception as error:
        st.session_state.error = f"식재료 인식 실패 — {error}"
        st.session_state.log = lines
    else:
        st.session_state.ingredients = result["ingredients"]
        st.session_state.vision_model = result["model"]
        st.session_state.log = result["log"]
        st.session_state.step = 2


def run_generation(items, cuisine, difficulty, time_limit, servings):
    st.session_state.error = ""
    st.session_state.recipes = []
    st.session_state.open_recipe = None
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
        detail = error.message if error.status == 200 else client.explain(error.status)
        st.session_state.error = f"레시피 추천 실패 — {detail}"
        st.session_state.log = lines
    except Exception as error:
        st.session_state.error = f"레시피 추천 실패 — {error}"
        st.session_state.log = lines
    else:
        st.session_state.recipes = result["recipes"]
        st.session_state.recipe_model = result["model"]
        st.session_state.log = result["log"]


# ---------- 레시피 카드와 상세 ----------

def render_recipe_cards():
    recipes = st.session_state.recipes
    for number, (column, item) in enumerate(zip(st.columns(len(recipes)), recipes)):
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
            if st.button("자세히 보기", key=f"open_{number}", use_container_width=True):
                st.session_state.open_recipe = number
                st.rerun()

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

    if st.session_state.user:
        if st.button("레시피 저장"):
            db.save_recipe(st.session_state.user["id"], item)
            st.toast(f"{item['title']} 저장했습니다")
    else:
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
    saved = db.get_profile(user["id"])

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
