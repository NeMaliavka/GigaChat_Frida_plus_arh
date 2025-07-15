import logging
import httpx
from app.config import BITRIX24_WEBHOOK_URL # Убедитесь, что импортируете ваш вебхук

# ... (тут может быть ваша функция make_b24_request, если вы ее вынесли)

async def cancel_booking(task_id: int, event_id: int) -> bool:
    """
    Отменяет бронирование, удаляя задачу и событие в календаре Bitrix24.
    
    :param task_id: ID задачи для удаления.
    :param event_id: ID события календаря для удаления.
    :return: True в случае успеха, False в случае ошибки.
    """
    logging.info(f"Начало отмены в Битрикс24. Задача: {task_id}, Событие: {event_id}")
    webhook_base_url = BITRIX24_WEBHOOK_URL.rstrip('/')
    
    async with httpx.AsyncClient(verify=False) as client:
        # Шаг 1: Удаление события календаря
        # Метод требует только ID события [7]
        event_params = {'id': event_id}
        try:
            event_res_raw = await client.post(f"{webhook_base_url}/calendar.event.delete", json=event_params)
            event_res_raw.raise_for_status()
            event_res = event_res_raw.json()
            
            # API возвращает {'result': True} при успехе
            if not event_res.get('result'):
                 logging.warning(f"Не удалось удалить событие (ID: {event_id}) или оно уже было удалено. Ответ: {event_res}")
                 # Не прерываем процесс, задача важнее
        except httpx.RequestError as e:
            logging.error(f"Ошибка сети при удалении события {event_id}: {e}")
            # Продолжаем, чтобы попытаться удалить хотя бы задачу
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP-ошибка при удалении события {event_id}: {e.response.text}")

        # Шаг 2: Удаление задачи
        # Метод требует taskId [9][11]
        task_params = {'taskId': task_id}
        try:
            task_res_raw = await client.post(f"{webhook_base_url}/tasks.task.delete", json=task_params)
            task_res_raw.raise_for_status()
            task_res = task_res_raw.json()

            # Успешное удаление задачи — главный критерий успеха всей операции
            if task_res.get('result') and task_res['result'].get('task'):
                logging.info(f"Задача (ID: {task_id}) и связанное событие (ID: {event_id}) успешно удалены.")
                return True
            else:
                logging.error(f"Не удалось удалить задачу (ID: {task_id}). Ответ API: {task_res}")
                return False
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logging.error(f"Критическая ошибка при удалении задачи {task_id}: {e}", exc_info=True)
            return False
            
    return False # Если что-то пошло совсем не так