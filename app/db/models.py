from pydantic import BaseModel
from datetime import datetime

class MessageHistory(BaseModel):
    """Модель для одного сообщения в истории диалога."""
    role: str # 'user' или 'assistant'
    content: str

class TrialLesson(BaseModel):
    """Модель для записи на пробный урок."""
    user_id: int
    child_name: str
    child_age: int
    phone_number: str
    status: str = "pending" # pending, confirmed, attended, missed
    created_at: datetime = datetime.now()

