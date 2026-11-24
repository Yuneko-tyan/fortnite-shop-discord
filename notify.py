
import os
import json
import sys
from datetime import datetime, timezone

import requests

API_URL = "https://itemshop.gg/api/v1/shop/fortnite"
WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
STATE_FILE = "state.json"

# Получаем актуальный магазин
response = requests.get(API_URL, timeout=20)
response.raise_for_status()

payload = response.json()
shop = payload["data"]

shop_date = shop["shopDate"]
today = datetime.now(timezone.utc).date().isoformat()

# Не отправляем старый магазин
if shop_date != today:
    print("Новый магазин пока не появился.")
    sys.exit(0)

# Читаем предыдущую дату магазина
try:
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)
except FileNotFoundError:
    state = {"last_shop_date": None}

if state.get("last_shop_date") == shop_date:
    print("Магазин уже отправлен.")
    sys.exit(0)

if shop.get("stale"):
    raise RuntimeError("API вернул устаревший магазин")

# Получаем изображения всех страниц магазина
images = shop.get("images", [])

if not images:
    raise RuntimeError("Изображения магазина пока недоступны")

# Ссылка на источник данных
source_url = (
    payload.get("meta", {})
    .get("attribution", {})
    .get("url", "https://itemshop.gg/fortnite")
)

# Формируем Discord Embed
embeds = [{
    "title": f"FORTNITE ITEM SHOP | {shop_date}",
    "description": (
        f"Магазин обновился!\n"
        f"Всего предметов: {shop.get('itemCount', 0)}\n\n"
        f"[Data from itemshop.gg]({source_url})"
    ),
    "image": {"url": images[0]}
}]

# Остальные страницы магазина
for image_url in images[1:]:
    embeds.append({
        "image": {"url": image_url}
    })

discord_payload = {
    "username": "Fortnite Item Shop",
    "content": "Магазин Fortnite обновился!",
    "embeds": embeds
}

# Отправляем уведомление
result = requests.post(
    WEBHOOK_URL,
    json=discord_payload,
    timeout=30
)

result.raise_for_status()

# Запоминаем дату только после успешной отправки
with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(
        {"last_shop_date": shop_date},
        f,
        indent=2
    )

print("Уведомление успешно отправлено!")
