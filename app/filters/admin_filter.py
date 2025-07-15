# app/filters/admin_filter.py
from aiogram.filters import BaseFilter
from aiogram.types import Message
# Убедитесь, что в конфиге есть список ID администраторов
from app.config import ADMIN_IDS

class IsAdmin(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in ADMIN_IDS
