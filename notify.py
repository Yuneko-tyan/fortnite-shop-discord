import os
import json
import time
import requests

from datetime import datetime, timezone
from urllib.parse import quote

API_URL = "https://itemshop.gg/api/v1/shop/fortnite"
WEBHOOK = os.environ["DISCORD_WEBHOOK_URL"]
STATE_FILE = "state.json"
ITEMSHOP_API_KEY = os.environ.get("ITEMSHOP_API_KEY", "").strip()

SHOP_PUSH_URL = "https://fortnite-favorites.kornouxova1998.workers.dev/shop"
SHOP_PUSH_SECRET = os.environ.get("SHOP_PUSH_SECRET", "").strip()

RARE_DAYS = 180

# Safety limits: prevent one slow API request from hanging the whole workflow.
SHOP_TIMEOUT = (5, 20)
WORKER_TIMEOUT = (5, 15)
WEBHOOK_TIMEOUT = (5, 20)
RARE_ITEM_TIMEOUT = (5, 8)
MAX_RARE_CHECKS = 20
MAX_RARE_CHECK_SECONDS = 180


def send_discord(payload):
    for attempt in range(5):
        response = requests.post(
            WEBHOOK,
            json=payload,
            timeout=WEBHOOK_TIMEOUT
        )

        if response.status_code == 429:
            delay = float(response.headers.get("Retry-After", 5))
            delay = min(delay, 30)
            print(f"Discord rate limit. Waiting {delay}s", flush=True)
            time.sleep(delay + 1)
            continue

        response.raise_for_status()
        return

    raise RuntimeError("Discord rate limit: retries exhausted")


def push_favorites(shop_date, items):
    if not SHOP_PUSH_SECRET:
        raise RuntimeError("Missing SHOP_PUSH_SECRET GitHub Secret")

    favorite_items = []
    seen_names = set()

    allowed_types = {
        "outfit", "emote", "backpack", "pickaxe",
        "wrap", "music", "jamtrack", "jam_track",
        "glider", "contrail", "instrument", "vehicle",
        "car", "body", "decal", "spray", "toy",
        "pet", "sidekick", "loadingscreen", "loading_screen",
        "banner", "emoji", "track", "consumable",
        "bundle"
    }

    for item in items:
        item_type = str(item.get("type") or "").lower().replace(" ", "")

        if item_type.startswith("jamtrack"):
            item_type = "music"

        if item_type not in allowed_types:
            continue

        name = str(item.get("name") or "").strip()
        
        normalized_type = (
            "music"
            if item_type.startswith("jamtrack")
            else "pet"
            if item_type == "sidekick"
            else item_type
        )

        key = f"{normalized_type}:{' '.join(name.lower().split())}"

        if not name or key in seen_names:
            continue

        seen_names.add(key)

        favorite_items.append({
            "name": name,
            "type": normalized_type
        })

    if not favorite_items:
        print("No supported items to send for personal favorites.", flush=True)
        return

    print(
        f"Sending {len(favorite_items)} items to favorites Worker...",
        flush=True
    )

    response = requests.post(
        SHOP_PUSH_URL,
        headers={"Authorization": f"Bearer {SHOP_PUSH_SECRET}"},
        json={"shop_date": shop_date, "items": favorite_items},
        timeout=WORKER_TIMEOUT
    )
    response.raise_for_status()

    result = response.json()
    print(
        "Personal favorite notifications: "
        f"sent={result.get('sent', 0)}, "
        f"failed={result.get('failed', 0)}, "
        f"skipped={result.get('skipped', 0)}",
        flush=True
    )


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
        "footer": {"text": f"Fortnite Item Shop • {shop_date}"}
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


def find_rare_returns(items, shop_date):
    if not ITEMSHOP_API_KEY:
        raise RuntimeError("Missing ITEMSHOP_API_KEY GitHub Secret")

    headers = {
        "Authorization": f"Bearer {ITEMSHOP_API_KEY}",
        "User-Agent": "FortniteShopDiscord/1.0"
    }

    outfit_items = [
        item for item in items
        if (item.get("type") or "").lower() == "outfit"
        and item.get("itemKey")
    ]

    if len(outfit_items) > MAX_RARE_CHECKS:
        print(
            f"Rare-return check limited to first {MAX_RARE_CHECKS} "
            f"of {len(outfit_items)} outfits.",
            flush=True
        )

    rare_items = []
    started = time.monotonic()

    for index, item in enumerate(outfit_items[:MAX_RARE_CHECKS], start=1):
        if time.monotonic() - started >= MAX_RARE_CHECK_SECONDS:
            print("Rare-return check stopped at its time limit.", flush=True)
            break

        item_key = item.get("itemKey")
        url = (
            "https://itemshop.gg/api/v1/items/fortnite/"
            + quote(item_key, safe=":")
        )

        print(
            f"Checking rare-return history {index}/"
            f"{min(len(outfit_items), MAX_RARE_CHECKS)}...",
            flush=True
        )

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=RARE_ITEM_TIMEOUT
            )

            if response.status_code == 404:
                continue

            response.raise_for_status()
            data = response.json()["data"]
            stays = data.get("stays", [])

            previous_stays = [
                stay for stay in stays
                if stay.get("state") == "past" and stay.get("end")
            ]

            if not previous_stays:
                continue

            last_end = max(stay["end"] for stay in previous_stays)
            last_date = datetime.fromisoformat(
                last_end.replace("Z", "+00:00")
            )
            current_date = datetime.fromisoformat(
                shop_date
            ).replace(tzinfo=timezone.utc)

            days_absent = (current_date - last_date).days

            if days_absent >= RARE_DAYS:
                rare_items.append({
                    "item": item,
                    "days": days_absent
                })

        except requests.RequestException as error:
            print(
                f"Could not check rare history for "
                f"{item.get('name', 'unknown')}: {error}",
                flush=True
            )
        except (KeyError, ValueError, TypeError) as error:
            print(
                f"Could not read rare history for "
                f"{item.get('name', 'unknown')}: {error}",
                flush=True
            )

    return rare_items


def send_batches(embeds, content):
    for index in range(0, len(embeds), 10):
        batch = embeds[index:index + 10]
        send_discord({
            "username": "Fortnite Item Shop",
            "content": content if index == 0 else "",
            "embeds": batch
        })


def main():
    print("Loading saved state...", flush=True)
    state = load_state()

    print("Downloading Fortnite shop...", flush=True)
    response = requests.get(API_URL, timeout=SHOP_TIMEOUT)
    response.raise_for_status()

    payload = response.json()
    shop = payload["data"]

    if shop.get("stale"):
        raise RuntimeError("Shop data is stale")

    shop_date = shop["shopDate"]

    already_sent = state["last_shop_date"] == shop_date

    attribution = (
        payload.get("meta", {})
        .get("attribution", {})
        .get("url", "https://itemshop.gg/fortnite")
    )

    print("Collecting shop items...", flush=True)
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

    print(f"Collected {len(items)} shop items.", flush=True)
    print(
    "PERFECT NIGHT ITEMS:",
    [
        {
            "name": item.get("name"),
            "type": item.get("type"),
            "itemKey": item.get("itemKey")
        }
        for item in items
        if "perfect night" in str(item.get("name") or "").lower()
    ],
    flush=True
)

    # Personal notifications must never block the existing public webhook.
    try:
        push_favorites(shop_date, items)
    except Exception as error:
        print(
            f"WARNING: Personal favorites notification failed: {error}",
            flush=True
        )

    if already_sent:
        print(
            "Shop already sent; personal favorites checked.",
            flush=True
        )
        return

    previous_keys = set(state.get("seen_item_keys", []))
    initialized = state.get("initialized", False)

    embeds = [
        make_embed(item, shop_date, attribution)
        for item in items
    ]

    if embeds:
        print("Sending complete shop to Discord...", flush=True)
        send_batches(
            embeds,
            f"🛒 **FORTNITE ITEM SHOP — {shop_date}**\n"
            f"Предметов в магазине: **{len(items)}**\n"
            f"Источник: {attribution}"
        )

    new_skins = []

    for item in items:
        item_type = (item.get("type") or "").lower()
        key = item.get("itemKey") or item.get("id")

        if item_type != "outfit":
            continue

        badge = (item.get("badge") or "").lower()
        is_new = (
            badge == "new"
            or (initialized and key not in previous_keys)
        )

        if is_new:
            new_skins.append(item)

    if new_skins:
        skin_embeds = []

        for item in new_skins:
            embed = make_embed(item, shop_date, attribution)
            embed["title"] = (
                "✨ НОВЫЙ СКИН: "
                + (item.get("name") or "Unknown")
            )[:256]
            skin_embeds.append(embed)

        send_batches(
            skin_embeds,
            "🚨 **НОВЫЕ СКИНЫ В МАГАЗИНЕ FORTNITE!**"
        )
        print(f"New skins: {len(new_skins)}", flush=True)
    else:
        print("No new skins", flush=True)

    print("Checking rare returning skins...", flush=True)
    rare_returns = find_rare_returns(items, shop_date)

    if rare_returns:
        rare_embeds = []

        for entry in rare_returns:
            item = entry["item"]
            days = entry["days"]
            embed = make_embed(item, shop_date, attribution)
            embed["title"] = (
                "🔥 РЕДКОЕ ВОЗВРАЩЕНИЕ: "
                + item.get("name", "Unknown")
            )[:256]
            embed["description"] += (
                f"\n\n⏳ **Не появлялся в магазине: {days} дней!**"
            )
            rare_embeds.append(embed)

        send_batches(
            rare_embeds,
            "💎 **РЕДКИЕ СКИНЫ ВЕРНУЛИСЬ В МАГАЗИН!**"
        )
        print(f"Rare returns found: {len(rare_returns)}", flush=True)
    else:
        print("No rare returns found (or some checks timed out).", flush=True)

    # Save state after the existing public notifications complete.
    state["last_shop_date"] = shop_date
    state["seen_item_keys"] = sorted(previous_keys | seen_in_shop)
    state["initialized"] = True
    save_state(state)

    print("Shop notification completed!", flush=True)


if __name__ == "__main__":
    main()
