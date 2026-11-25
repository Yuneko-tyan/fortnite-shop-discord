import json
import urllib.request
import urllib.error
from getpass import getpass

APP_ID = input("Введи Application ID: ").strip()
BOT_TOKEN = getpass("Введи Bot Token (ввод скрыт): ").strip()
GUILD_ID = "1277175997267181618"

commands = [
    {
        "name": "favorite",
        "description": "Управление избранными скинами Fortnite",
        "options": [
            {
                "type": 1,
                "name": "add",
                "description": "Добавить скин в избранное",
                "options": [{
                    "type": 3,
                    "name": "name",
                    "description": "Название скина",
                    "required": True
                }]
            },
            {
                "type": 1,
                "name": "remove",
                "description": "Удалить скин из избранного",
                "options": [{
                    "type": 3,
                    "name": "name",
                    "description": "Название скина",
                    "required": True
                }]
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
        "description": "Настроить уведомления о любимых скинах",
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
    "Content-Type": "application/json"
}

for command in commands:
    data = json.dumps(command).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST"
    )

    try:
        with urllib.request.urlopen(request) as response:
            print(f"Успешно: /{command['name']} — HTTP {response.status}")

    except urllib.error.HTTPError as error:
        print(f"Ошибка /{command['name']}: HTTP {error.code}")
        print(error.read().decode("utf-8"))

print("Регистрация завершена.")
