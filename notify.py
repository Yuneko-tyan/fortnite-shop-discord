
from datetime import datetime, timezone
from urllib.parse import quote
import os
import json
import time
import requests

API_URL = "https://itemshop.gg/api/v1/shop/fortnite"
WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
STATE_FILE = "state.json"
ITEMSHOP_API_KEY = os.environ.get(
    "ITEMSHOP_API_KEY", ""
).strip()

def send_discord(payload):
    for attempt in range(5):
        response = requests.post(
            WEBHOOK,
            json=payload,
            timeout=30
        )

        if response.status_code == 429:
            delay = float(
                response.headers.get("Retry-After", 5)
            )
            print(f"Rate limit. Waiting {delay}s")
            time.sleep(delay + 1)
            continue

        response.raise_for_status()
        return

    raise RuntimeError("Discord rate limit: retries exhausted")


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "last_shop_date": None,
            "seen_item_keys": [],
            "initialized": False
        }


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def price_text(item):
    price = item.get("price") or {}

    amount = price.get("amount")
    currency = price.get("currency") or "V-Bucks"

    if amount is None:
        return price.get("label") or "Цена неизвестна"

    formatted = f"{amount:,}".replace(",", " ")

    result = f"{formatted} {currency}"

    regular = price.get("regular")
    if regular and regular > amount:
        result += f"\n~~{regular:,} {currency}~~".replace(",", " ")

    return result


def rarity_color(item):
    rarity = item.get("rarity") or {}
    color = rarity.get("color", "#5865F2")

    try:
        return int(color.replace("#", ""), 16)
    except (ValueError, AttributeError):
        return 0x5865F2


def make_embed(item, shop_date, attribution):
    ITEMSHOP_API_KEY = os.environ.get("ITEMSHOP_API_KEY", "").strip()
    RARE_DAYS = 180


def find_rare_returns(items, shop_date):
    if not ITEMSHOP_API_KEY:
        raise RuntimeError(
            "Missing ITEMSHOP_API_KEY GitHub Secret"
        )

    headers = {
        "Authorization": f"Bearer {ITEMSHOP_API_KEY}",
        "User-Agent": "FortniteShopDiscord/1.0"
    }


    rare_items = []

    for item in items:
        if (item.get("type") or "").lower() != "outfit":
            continue

        item_key = item.get("itemKey")

        if not item_key:
            continue

        url = (
            "https://itemshop.gg/api/v1/items/fortnite/"
            + quote(item_key, safe=":")
        )

        response = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        if response.status_code == 404:
            continue

        response.raise_for_status()

        data = response.json()["data"]
        stays = data.get("stays", [])

        # Ignore current appearance and find previous visits
        previous_stays = [
            stay for stay in stays
            if stay.get("state") == "past"
            and stay.get("end")
        ]

        if not previous_stays:
            continue

        last_end = max(
            stay["end"] for stay in previous_stays
        )

        last_date = datetime.fromisoformat(
            last_end.replace("Z", "+00:00")
        )

        current_date = datetime.fromisoformat(
            shop_date
        ).replace(tzinfo=timezone.utc)

        days_absent = (
            current_date - last_date
        ).days

        if days_absent >= RARE_DAYS:
            rare_items.append({
                "item": item,
                "days": days_absent
            })

    return rare_items

    rarity = item.get("rarity") or {}
    images = item.get("images") or {}

    name = item.get("name") or "Unknown item"
    item_type = item.get("type") or "Cosmetic"

    embed = {
        "title": name[:256],
        "description": (
            f"**Тип:** {item_type}\n"
            f"**Редкость:** {rarity.get('name', 'Unknown')}\n"
            f"**Цена:** {price_text(item)}"
        ),
        "color": rarity_color(item),
        "footer": {
            "text": f"Fortnite Item Shop • {shop_date}"
        }
    }

    if images.get("card"):
        embed["image"] = {"url": images["card"]}
    elif images.get("render"):
        embed["thumbnail"] = {"url": images["render"]}

    if item.get("sourceUrl"):
        embed["url"] = item["sourceUrl"]

    if attribution:
        embed["author"] = {
            "name": "Data from itemshop.gg",
            "url": attribution
        }

    return embed


def send_batches(embeds, content):
    for index in range(0, len(embeds), 10):
        batch = embeds[index:index + 10]

        send_discord({
            "username": "Fortnite Item Shop",
            "content": content if index == 0 else "",
            "embeds": batch
        })


def main():
    state = load_state()

    response = requests.get(API_URL, timeout=30)
    response.raise_for_status()

    payload = response.json()
    shop = payload["data"]

    if shop.get("stale"):
        raise RuntimeError("Shop data is stale")

    shop_date = shop["shopDate"]

    if state["last_shop_date"] == shop_date:
        print("Shop already sent")
        return

    attribution = (
        payload.get("meta", {})
        .get("attribution", {})
        .get("url", "https://itemshop.gg/fortnite")
    )

    # Collect items from all shop sections
    items = []
    seen_in_shop = set()

    for section in shop.get("sections", []):
        if section.get("upcoming"):
            continue

        for item in section.get("items", []):
            key = item.get("itemKey") or item.get("id")

            if not key or key in seen_in_shop:
                continue

            if item.get("soldOut"):
                continue

            seen_in_shop.add(key)
            items.append(item)

    # Previous item database
    previous_keys = set(state.get("seen_item_keys", []))
    initialized = state.get("initialized", False)

    embeds = [
        make_embed(item, shop_date, attribution)
        for item in items
    ]

    # Send the complete shop as item cards
    if embeds:
        send_batches(
            embeds,
            f"🛒 **FORTNITE ITEM SHOP — {shop_date}**\n"
            f"Предметов в магазине: **{len(items)}**\n"
            f"Источник: {attribution}"
        )

    # Find new outfits
    new_skins = []

    for item in items:
        item_type = (item.get("type") or "").lower()
        key = item.get("itemKey") or item.get("id")

        if item_type != "outfit":
            continue

        badge = (item.get("badge") or "").lower()

        # On first launch, use the API's New badge.
        # On later launches, detect previously unseen outfits.
        is_new = (
            badge == "new"
            or (initialized and key not in previous_keys)
        )

        if is_new:
            new_skins.append(item)

    # Separate notification for new skins
    if new_skins:
        skin_embeds = []

        for item in new_skins:
            embed = make_embed(
                item,
                shop_date,
                attribution
            )

            embed["title"] = (
                "✨ НОВЫЙ СКИН: " +
                (item.get("name") or "Unknown")
            )[:256]

            skin_embeds.append(embed)

        send_batches(
            skin_embeds,
            "🚨 **НОВЫЕ СКИНЫ В МАГАЗИНЕ FORTNITE!**"
        )

        print(f"New skins: {len(new_skins)}")
    else:
        print("No new skins")

    
    # Find rare returning skins
    rare_returns = find_rare_returns(
        items,
        shop_date
    )

    if rare_returns:
        rare_embeds = []

        for entry in rare_returns:
            item = entry["item"]
            days = entry["days"]

            embed = make_embed(
                item,
                shop_date,
                attribution
            )

            embed["title"] = (
                "🔥 РЕДКОЕ ВОЗВРАЩЕНИЕ: "
                + item.get("name", "Unknown")
            )[:256]

            embed["description"] += (
                f"\n\n⏳ **Не появлялся в магазине: "
                f"{days} дней!**"
            )

            rare_embeds.append(embed)

        send_batches(
            rare_embeds,
            "💎 **РЕДКИЕ СКИНЫ ВЕРНУЛИСЬ В МАГАЗИН!**"
        )

        print(
            f"Rare returns found: {len(rare_returns)}"
        )

    # Save state only after successful notifications
    state["last_shop_date"] = shop_date
    state["seen_item_keys"] = sorted(
        previous_keys | seen_in_shop
    )
    state["initialized"] = True

    save_state(state)

    print("Shop notification completed!")


if __name__ == "__main__":
    main()
