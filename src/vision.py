"""PRD 1단계 — 냉장고 사진에서 식재료를 알아보는 부분.

화면과 떼어 둔 순수 모듈이라 Streamlit 없이도 시험할 수 있다.
"""

import base64
import io

from PIL import Image

from client import call_with_fallback, parse_json

VISION_MODELS = [
    "google/gemma-4-26b-a4b-it:free",        # 수업 선정 모델
    "minimax/minimax-m3.1-flash:free",       # 예비 1
    "nvidia/nemotron-3.5-super-vl:free",     # 예비 2
    "dots-studio/dots-3-note-preview:free",  # 예비 3
]

CATEGORIES = ["채소", "과일", "육류", "해산물", "유제품/계란", "조미료", "음료", "기타"]
UNITS = ["개", "병", "봉지", "팩", "단", "g", "kg", "ml", "L", "기타"]

MAX_EDGE = 1024
JPEG_QUALITY = 85

PROMPT = (
    "이 냉장고 사진에서 보이는 식재료를 모두 찾아 JSON 으로만 답하세요.\n"
    "설명이나 인사말을 쓰지 말고 JSON 만 쓰세요.\n\n"
    '형식: {"ingredients": [{"name": "재료 이름", "quantity": 숫자, '
    '"unit": "단위", "category": "분류"}]}\n\n'
    f"- name 은 한국어로 씁니다.\n"
    f"- quantity 는 숫자입니다. 셀 수 없으면 1 로 씁니다.\n"
    f"- unit 은 다음 중 하나입니다: {', '.join(UNITS)}\n"
    f"- category 는 다음 중 하나입니다: {', '.join(CATEGORIES)}\n"
    "- 보이지 않는 재료를 지어내지 마세요."
)


def resize_image(data, max_edge=MAX_EDGE, quality=JPEG_QUALITY):
    """긴 변을 max_edge 까지 줄이고 JPEG 로 다시 압축함.

    (줄인 바이트, 원래 크기, 줄인 크기, 원래 바이트 수, 줄인 바이트 수) 를 돌려준다.
    """
    image = Image.open(io.BytesIO(data))
    original_size = image.size
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    longest = max(image.size)
    if longest > max_edge:
        ratio = max_edge / longest
        new_size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
        image = image.resize(new_size, Image.LANCZOS)

    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
    shrunk = buffer.getvalue()
    return shrunk, original_size, image.size, len(data), len(shrunk)


def build_messages(jpeg_bytes):
    encoded = base64.b64encode(jpeg_bytes).decode()
    return [{"role": "user", "content": [
        {"type": "text", "text": PROMPT},
        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}},
    ]}]


def normalize(items):
    """모델이 돌려준 목록을 화면이 믿고 쓸 수 있는 모양으로 다듬음.

    같은 이름이 거듭 나오면 수량을 합쳐 하나로 묶는다 (노트 6.4.11.1목).
    재료마다 고유 `_id` 를 붙인다. 화면 위젯 key 로 순번을 쓰면 가운데 항목을
    지울 때 엉뚱한 것이 지워진다 (노트 6.4.11.4목).
    """
    cleaned = []
    seen = {}
    for item in items:
        if isinstance(item, str):
            item = {"name": item}
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        try:
            quantity = int(float(item.get("quantity", 1)))
        except (TypeError, ValueError):
            quantity = 1
        quantity = max(1, quantity)
        unit = str(item.get("unit") or "개").strip()
        if unit not in UNITS:
            unit = "기타"
        category = str(item.get("category") or "기타").strip()
        if category not in CATEGORIES:
            category = "기타"
        key = (name, unit)
        if key in seen:
            seen[key]["quantity"] += quantity
            continue
        entry = {"_id": f"{len(cleaned)}-{name}", "name": name, "quantity": quantity,
                 "unit": unit, "category": category}
        seen[key] = entry
        cleaned.append(entry)
    return cleaned


def recognize(image_bytes, api_key, models=None, on_event=None):
    """사진에서 식재료를 알아봄.

    돌려주는 값: {"ingredients": [...], "model": 쓴 모델, "log": 진행 기록,
                 "original_bytes": .., "resized_bytes": ..}
    실패하면 client.ModelError 또는 ValueError 를 올린다.
    """
    jpeg, original_size, new_size, before, after = resize_image(image_bytes)
    if on_event:
        on_event(
            f"사진 줄이기: {original_size[0]}x{original_size[1]} {before // 1024}KB"
            f" -> {new_size[0]}x{new_size[1]} {after // 1024}KB"
        )

    model, content, log = call_with_fallback(
        list(models) if models else VISION_MODELS,
        build_messages(jpeg), api_key, max_tokens=4000, on_event=on_event,
    )
    data = parse_json(content)
    ingredients = normalize(data.get("ingredients") or [])
    if not ingredients:
        raise ValueError("재료를 하나도 찾지 못했습니다. 다른 사진으로 다시 해 보세요.")
    return {
        "ingredients": ingredients,
        "model": model,
        "log": log,
        "original_bytes": before,
        "resized_bytes": after,
    }
