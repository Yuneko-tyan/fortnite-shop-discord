import json
import urllib.request
import urllib.error
from getpass import getpass

APP_ID = input("Введи Application ID: ").strip()
BOT_TOKEN = getpass("Введи Bot Token (ввод скрыт): ").strip()
GUILD_ID = "1277175997267181618"

if not APP_ID.isdigit():
    raise SystemExit("Ошибка: Application ID должен состоять только из цифр.")

commands = [
  {
    "name": "favorite",
    "description": "Управление избранными предметами Fortnite",
    "options": [
        {
            "type": 1,
            "name": "add",
            "description": "Добавить предмет в избранное",
            "options": [
                {
                    "type": 3,
                    "name": "name",
                    "description": "Название предмета",
                    "required": True
                },
                {
                    "type": 3,
                    "name": "item_type",
                    "description": "Категория предмета",
                    "required": True,
                    "choices": [
                        {"name": "Скин", "value": "outfit"},
                        {"name": "Питомец", "value": "pet"},
                        {"name": "Эмоция", "value": "emote"},
                        {"name": "Музыка", "value": "music"},
                        {"name": "Кирка", "value": "pickaxe"},
                        {"name": "Рюкзак", "value": "backpack"},
                        {"name": "Дельтаплан", "value": "glider"},
                        {"name": "Обёртка", "value": "wrap"},
                        {"name": "След", "value": "contrail"},
                        {"name": "Инструмент", "value": "instrument"},
                        {"name": "Транспорт", "value": "vehicle"}
                    ]
                }
            ]
        },
            {
                "type": 1,
                "name": "remove",
                "description": "Удалить предмет из избранного",
                "options": [
    {
        "type": 3,
        "name": "name",
        "description": "Название предмета Fortnite",
        "required": True
    },
    {
        "type": 3,
        "name": "item_type",
        "description": "Категория предмета",
        "required": True,
        "choices": [
            {"name": "Скин", "value": "outfit"},
            {"name": "Эмоция", "value": "emote"},
            {"name": "Музыка", "value": "music"},
            {"name": "Кирка", "value": "pickaxe"},
            {"name": "Рюкзак", "value": "backpack"},
            {"name": "Дельтаплан", "value": "glider"},
            {"name": "Обёртка", "value": "wrap"},
            {"name": "След", "value": "contrail"},
            {"name": "Инструмент", "value": "instrument"},
            {"name": "Транспорт", "value": "vehicle"}
        ]
    }
]
            },
            {
                "type": 1,
                "name": "list",
                "description": "Показать своё избранное"
            },
            {
                "type": 1,
                "name": "clear",
                "description": "Очистить своё избранное"
            }
        ]
    },
    {
        "name": "notify",
        "description": "Настроить уведомления о любимых предметах",
        "options": [
            {
                "type": 3,
                "name": "mode",
                "description": "Куда отправлять уведомления",
                "required": True,
                "choices": [
                    {"name": "Личные сообщения", "value": "dm"},
                    {"name": "В канал", "value": "channel"}
                ]
            },
            {
                "type": 7,
                "name": "channel",
                "description": "Канал для уведомлений (если выбран режим «В канал»)",
                "required": False
            }
        ]
    },
    {
        "name": "shop",
        "description": "Посмотреть настройки уведомлений Fortnite Shop"
    }
]

url = (
    f"https://discord.com/api/v10/applications/"
    f"{APP_ID}/guilds/{GUILD_ID}/commands"
)

headers = {
    "Authorization": f"Bot {BOT_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
    # Discord requires a valid User-Agent for API clients.
    "User-Agent": "DiscordBot (https://discord.com, 1.0)"
}

success_count = 0

for command in commands:
    data = json.dumps(command, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            print(f"Успешно: /{command['name']} — HTTP {response.status}")
            success_count += 1

    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        print(f"Ошибка /{command['name']}: HTTP {error.code}")
        print(details)

    except urllib.error.URLError as error:
        print(f"Не удалось подключиться при регистрации /{command['name']}.")
        print(f"Подробности: {error.reason}")

print()
if success_count == len(commands):
    print("Готово! Все 3 команды зарегистрированы.")
else:
    print(f"Зарегистрировано команд: {success_count} из {len(commands)}.")
    print("Если снова появится Cloudflare 1010, пришли скриншот ошибки.")
