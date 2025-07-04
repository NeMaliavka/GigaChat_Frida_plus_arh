import logging

# Примерная структура для работы с Bitrix24 API
# Потребуется установить библиотеку, например, `bitrix24-python-rest`

class Bitrix24Client:
    def __init__(self, webhook_url: str):
        # self.bx24 = Bitrix24(webhook_url)
        self.webhook_url = webhook_url
        logging.info("Клиент Bitrix24 инициализирован (заглушка).")

    def create_lead(self, name: str, phone: str, age: int, source: str = "Telegram Bot") -> int:
        """
        Создает лид в Bitrix24.
        Возвращает ID созданного лида.
        """
        fields = {
            "TITLE": f"Заявка на пробный урок от {name}",
            "NAME": name,
            "PHONE": [{"VALUE": phone, "VALUE_TYPE": "WORK"}],
            "UF_CRM_CHILD_AGE": age, # Пример пользовательского поля
            "SOURCE_ID": source,
        }
        
        logging.info(f"Создание лида в Bitrix24 (заглушка): {fields}")
        # try:
        #     result = self.bx24.callMethod('crm.lead.add', fields=fields)
        #     logging.info(f"Лид успешно создан, ID: {result}")
        #     return int(result)
        # except Exception as e:
        #     logging.error(f"Ошибка создания лида в Bitrix24: {e}")
        #     return 0
        
        # Возвращаем случайный ID для демонстрации
        import random
        return random.randint(100, 999)

# Пример инициализации клиента
# B24_WEBHOOK = os.getenv("BITRIX24_WEBHOOK_URL")
# b24_client = Bitrix24Client(B24_WEBHOOK) if B24_WEBHOOK else None
