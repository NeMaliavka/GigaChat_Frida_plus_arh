# import requests

# webhook_url = 'https://b24-aq3cu2.bitrix24.ru/rest/1/cuq4un14clczb58j/calendar.event.delete.json'

# data = {'id': 2}

# respons = requests.post(webhook_url, json=data)
# event = respons.json()
# print(event)


# #calendar.event.delete
# #calendar.event.getbyid
import asyncio
import aiohttp
import logging

# --- КОНФИГУРАЦИЯ ---
# URL вашего входящего вебхука. Должен заканчиваться на слэш "/"
BITRIX24_WEBHOOK_URL = "https://b24-aq3cu2.bitrix24.ru/rest/1/cuq4un14clczb58j/"
# ID пользователя, чьи события календаря нужно удалить
USER_ID = 1
# Пауза между запросами на удаление, чтобы не превысить лимиты API
DELETE_DELAY_SECONDS = 0.5

# Настройка логирования для отслеживания процесса
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- УНИВЕРСАЛЬНЫЕ ФУНКЦИИ ---

async def fetch_all_ids(session, method, params=None):
    """Асинхронно получает все ID, обрабатывая пагинацию и разные ключи ID."""
    all_ids = []
    start = 0
    while True:
        current_params = params.copy() if params else {}
        current_params['start'] = start

        async with session.post(f"{BITRIX24_WEBHOOK_URL}{method}", json=current_params) as response:
            if response.status != 200:
                logging.error(f"Ошибка API {method}: {response.status}, {await response.text()}")
                break
            
            data = await response.json()

            if 'error' in data:
                logging.error(f"Ошибка выполнения метода {method}: {data.get('error_description', 'No description')}")
                break
            
            result = data.get('result', {})
            
            items = []
            if method == 'calendar.event.get' and isinstance(result, list):
                items = result
            elif method == 'tasks.task.list' and 'tasks' in result and isinstance(result.get('tasks'), list):
                items = result['tasks']

            if not items:
                logging.info(f"Больше элементов для {method} не найдено.")
                break
            
            item_ids = []
            for item in items:
                if 'id' in item:
                    item_ids.append(item['id'])
                elif 'ID' in item:
                    item_ids.append(item['ID'])

            if not item_ids:
                logging.warning(f"В полученных элементах для {method} не найдены ID.")
                break

            all_ids.extend(item_ids)
            logging.info(f"Получено {len(item_ids)} ID. Всего собрано: {len(all_ids)}")

            if 'next' in data:
                start = data['next']
            else:
                break

    return all_ids

async def delete_items_by_id(session, method, id_key, ids, extra_params=None):
    """Асинхронно удаляет элементы по списку их ID."""
    if not ids:
        logging.warning(f"Нет ID для удаления методом {method}.")
        return

    logging.info(f"Начинается удаление {len(ids)} элементов методом {method}...")
    for item_id in ids:
        params = {id_key: item_id}
        if extra_params:
            params.update(extra_params)
        
        async with session.post(f"{BITRIX24_WEBHOOK_URL}{method}", json=params) as response:
            if response.status == 200:
                result = await response.json()
                if 'result' in result and result['result']:
                     logging.info(f"Элемент с ID {item_id} успешно удален.")
                else:
                     logging.warning(f"Не удалось удалить элемент с ID {item_id}. Ответ: {result}")
            else:
                logging.error(f"Ошибка API при удалении элемента {item_id}: {response.status}, {await response.text()}")
        
        await asyncio.sleep(DELETE_DELAY_SECONDS)
    logging.info(f"Удаление элементов методом {method} завершено.")


async def main():
    """Основная функция для сбора и удаления данных."""
    async with aiohttp.ClientSession() as session:
        logging.info("--- Начинаем сбор ID задач ---")
        task_ids = await fetch_all_ids(session, 'tasks.task.list')
        logging.info(f"--- Всего найдено задач: {len(task_ids)} ---")

        logging.info("\n--- Начинаем сбор ID событий календаря ---")
        event_params = {'type': 'user', 'ownerId': USER_ID}
        event_ids = await fetch_all_ids(session, 'calendar.event.get', params=event_params)
        logging.info(f"--- Всего найдено событий: {len(event_ids)} ---")
        
        # --- ИСПРАВЛЕНИЕ ЗДЕСЬ: УДАЛЕНИЕ ДУБЛИКАТОВ ---
        unique_task_ids = list(set(task_ids))
        unique_event_ids = list(set(event_ids))
        
        if len(task_ids) != len(unique_task_ids):
            logging.info(f"Удалены дубликаты ID задач. Было: {len(task_ids)}, стало: {len(unique_task_ids)}")
        if len(event_ids) != len(unique_event_ids):
            logging.info(f"Удалены дубликаты ID событий. Было: {len(event_ids)}, стало: {len(unique_event_ids)}")


        if not unique_task_ids and not unique_event_ids:
            logging.info("Задачи и события для удаления не найдены. Завершение работы.")
            return

        try:
            confirm = input(
                f"\n!!! ВНИМАНИЕ !!!\n"
                f"Найдено {len(unique_task_ids)} уникальных задач и {len(unique_event_ids)} уникальных событий для удаления.\n"
                f"Это действие НЕОБРАТИМО. Вы уверены, что хотите продолжить? (введите 'yes'): "
            )
        except (EOFError, KeyboardInterrupt):
            print("\nОперация отменена пользователем.")
            return

        if confirm.lower() != 'yes':
            print("Операция отменена.")
            return

        # Удаляем задачи
        await delete_items_by_id(session, 'tasks.task.delete', 'taskId', unique_task_ids)

        # Удаляем события
        event_delete_params = {'type': 'user', 'ownerId': USER_ID}
        await delete_items_by_id(session, 'calendar.event.delete', 'id', unique_event_ids, extra_params=event_delete_params)

        logging.info("\nВсе операции завершены.")

if __name__ == "__main__":
    asyncio.run(main())
