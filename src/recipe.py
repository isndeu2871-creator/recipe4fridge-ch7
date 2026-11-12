"""PRD 2단계 — 식재료로 레시피를 추천한다."""

from client import call_with_fallback, parse_json

TEXT_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",  # 수업 선정 모델
    "minimax/minimax-m3.1-flash:free",         # 예비 1
    "openrouter/free",                         # 예비 2
    "cohere/north-mini-code:free",             # 예비 3
]

ANY = "상관없음"

CUISINE_OPTIONS = [ANY, "한식", "양식", "중식", "일식"]
DIFFICULTY_OPTIONS = [ANY, "초급", "중급", "고급"]
TIME_OPTIONS = [ANY, "15분 이내", "30분 이내", "30분 이상"]
SERVING_OPTIONS = [ANY, 1, 2, 3, 4]


def build_prompt(ingredients, cuisine, difficulty, time_limit, servings):
    listed = ", ".join(
        f"{item['name']} {item['quantity']}{item['unit']}" for item in ingredients
    )
    # `상관없음` 은 조건으로 걸지 않는다. 걸면 모델이 그 말을 요리 종류로 읽는다.
    conditions = []
    if cuisine != ANY:
        conditions.append(f"종류: {cuisine}")
    if difficulty != ANY:
        conditions.append(f"난이도: {difficulty}")
    if time_limit != ANY:
        conditions.append(f"조리 시간: {time_limit}")
    if servings != ANY:
        conditions.append(f"인원: {servings}인분")
    condition_line = (" / ".join(conditions) + "\n") if conditions else "조건 없음\n"

    return (
        "아래 재료로 만들 수 있는 레시피 3개를 JSON 으로만 답하세요.\n"
        "설명이나 인사말 없이 JSON 만 쓰세요.\n"
        "모든 글자는 반드시 한국어로 씁니다. 영어로 쓰지 마세요.\n\n"
        f"재료: {listed}\n"
        f"{condition_line}\n"
        '형식: {"recipes": [{"title": "요리 이름", "cuisine": "한식", '
        '"difficulty": "초급", "time_minutes": 20, "servings": 2, '
        '"used_ingredients": ["..."], "missing_ingredients": ["..."], '
        '"steps": ["1단계", "2단계"]}]}\n\n'
        "- used_ingredients 는 위 재료 중 실제로 쓰는 것만 적습니다.\n"
        "- missing_ingredients 는 위 재료에 없지만 필요한 것을 적습니다. 없으면 빈 목록.\n"
        "- steps 는 3개 이상 적습니다."
    )


def normalize(items, cuisine, difficulty, servings):
    cleaned = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        try:
            minutes = int(float(item.get("time_minutes", 0)))
        except (TypeError, ValueError):
            minutes = 0
        try:
            portions = int(item.get("servings") or (servings if servings != ANY else 2))
        except (TypeError, ValueError):
            portions = 2
        cleaned.append({
            "title": title,
            "cuisine": str(item.get("cuisine") or (cuisine if cuisine != ANY else "")),
            "difficulty": str(item.get("difficulty") or (difficulty if difficulty != ANY else "")),
            "time_minutes": max(0, minutes),
            "servings": portions,
            "used_ingredients": [str(x) for x in (item.get("used_ingredients") or [])],
            "missing_ingredients": [str(x) for x in (item.get("missing_ingredients") or [])],
            "steps": [str(x) for x in (item.get("steps") or []) if str(x).strip()],
        })
    return cleaned


def generate(ingredients, cuisine, difficulty, time_limit, servings,
             api_key, models=None, on_event=None):
    """레시피를 만든다. {"recipes": [...], "model": .., "log": [..]} 를 돌려준다."""
    if not ingredients:
        raise ValueError("재료가 없습니다. 1단계를 먼저 끝내세요.")

    prompt = build_prompt(ingredients, cuisine, difficulty, time_limit, servings)
    model, content, log = call_with_fallback(
        list(models) if models else TEXT_MODELS,
        [{"role": "user", "content": prompt}],
        api_key, max_tokens=4000, on_event=on_event,
    )
    data = parse_json(content)
    recipes = normalize(data.get("recipes") or [], cuisine, difficulty, servings)
    if not recipes:
        raise ValueError("레시피를 받지 못했습니다. 다시 시도해 보세요.")
    return {"recipes": recipes, "model": model, "log": log}
