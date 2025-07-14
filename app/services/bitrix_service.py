import httpx
import logging
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
import asyncio

from app.config import BITRIX24_WEBHOOK_URL, GROUP_ID

try:
    from app.utils.text_tools import inflect_name
    MORPHOLOGY_ENABLED = True
except ImportError:
    logging.warning("Утилиты склонения не найдены, имена в задачах будут в именительном падеже.")
    MORPHOLOGY_ENABLED = False
    # Создаем заглушку, чтобы код не падал

async def check_b24_connection():
    """
    Отправляет тестовый запрос к API Битрикс24 для проверки соединения.
    """
    # --- ИСПРАВЛЕНИЕ: Используем переменную напрямую ---
    if not BITRIX24_WEBHOOK_URL:
        logging.error("URL вебхука Битрикс24 (BITRIX24_WEBHOOK_URL) не настроен в .env файле.")
        return None

    api_method = "app.info"
    url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{api_method}"

    try:
        # Для коробочных версий оставляем verify=False
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(url)
            response.raise_for_status()
            data = response.json()
            
            if 'result' in data:
                logging.info("Соединение с Битрикс24 успешно установлено!")
                api_version = data['result'].get('VERSION', 'недоступна (стандартно для вебхука)')
                logging.info(f"Версия REST API: {api_version}")
                return data['result']
            else:
                logging.error(f"Ошибка при запросе к Битрикс24: {data.get('error_description') or data}")
                return None

    except httpx.RequestError as e:
        logging.error(f"Ошибка HTTP-запроса к Битрикс24: {e}")
        return None

# Этот блок для самостоятельного тестирования файла оставляем, он полезен
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Перед запуском этого файла убедись, что .env файл доступен из корня проекта
    asyncio.run(check_b24_connection())

def _parse_b24_date(date_str: str, tz: ZoneInfo):
    """
    Вспомогательная функция для надежного распознавания форматов дат от Битрикс24.
    """
    # Сначала пробуем стандартный для порталов формат ДД.ММ.ГГГГ
    try:
        naive_dt = datetime.strptime(date_str, '%d.%m.%Y %H:%M:%S')
        # Делаем время "осведомленным" о часовом поясе
        return naive_dt.replace(tzinfo=tz)
    except (ValueError, TypeError):
        # Если не получилось, пробуем стандартный формат API (ISO)
        try:
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            logging.warning(f"Не удалось распознать формат даты: '{date_str}'. Событие будет пропущено.")
            return None

async def get_free_slots(from_date: datetime, to_date: datetime, user_ids: list[int], lesson_duration: int = 60):
    """
    УЛУЧШЕННАЯ ВЕРСИЯ.
    Получает свободные слоты, надежно распознавая разные форматы дат от Битрикс24.
    """
    api_method = "calendar.event.get"
    url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{api_method}"
    work_hours = {'start': 10, 'end': 18}
    final_slots = {}
    portal_tz = from_date.tzinfo  # Получаем часовой пояс из запроса

    try:
        async with httpx.AsyncClient(verify=False) as client:
            for user_id in user_ids:
                params = {
                    'type': 'user', 'ownerId': str(user_id),
                    'from': from_date.isoformat(), 'to': to_date.isoformat(),
                }
                response = await client.post(url, json=params)
                response.raise_for_status()
                data = response.json()

                if 'result' not in data:
                    logging.error(f"Ошибка API при получении событий для user_id {user_id}: {data.get('error_description') or data}")
                    continue

                busy_intervals = []
                for event in data.get('result', []):
                    # Используем наш новый надежный парсер
                    start_busy = _parse_b24_date(event.get('DATE_FROM'), portal_tz)
                    end_busy = _parse_b24_date(event.get('DATE_TO'), portal_tz)
                    
                    if start_busy and end_busy:
                        busy_intervals.append((start_busy, end_busy))

                # Дальнейшая логика вычисления свободных слотов (она у вас корректна)
                for day_offset in range((to_date - from_date).days + 1):
                    check_day = (from_date + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
                    if check_day.weekday() >= 5:  # Пропускаем Сб и Вс
                        continue

                    for hour in range(work_hours['start'], work_hours['end']):
                        slot_start = check_day.replace(hour=hour, minute=0)
                        slot_end = slot_start + timedelta(minutes=lesson_duration)

                        if slot_end.hour > work_hours['end'] or slot_start < datetime.now(portal_tz):
                            continue

                        is_free = True
                        for busy_start, busy_end in busy_intervals:
                            if slot_start < busy_end and busy_start < slot_end:
                                is_free = False
                                break
                        
                        if is_free:
                            date_key = slot_start.strftime('%Y-%m-%d')
                            if date_key not in final_slots:
                                final_slots[date_key] = []
                            final_slots[date_key].append({'time': slot_start.strftime('%H:%M'), 'user_id': user_id})

            # Сортируем итоговые слоты по времени
            for date_key in final_slots:
                final_slots[date_key] = sorted(final_slots[date_key], key=lambda x: x['time'])

            return final_slots

    except httpx.RequestError as e:
        logging.error(f"Критическая HTTP ошибка при запросе событий: {e}")
        return {} # В случае ошибки возвращаем пустой словарь
    except Exception as e:
        logging.error(f"Непредвиденная ошибка в get_free_slots: {e}")
        return {}


try:
    from app.utils.text_tools import inflect_name
except ImportError:
    def inflect_name(name, case): return name # Заглушка, если утилиты нет

async def book_lesson(user_id: int, start_time: datetime, duration_minutes: int, client_data: dict):    
    """
    Бронирует урок: ПРОВЕРЯЕТ доступность слота, СОЗДАЕТ задачу и связанное СОБЫТИЕ.
    Это атомарно защищает от двойного бронирования.
    - Добавлено детальное логирование.
    - Исправлена структура запроса для calendar.event.add (добавлено поле 'fields').
    - Всегда возвращает кортеж (task_id, teacher_name) или (None, None).
    - Использует ВЕРХНИЙ РЕГИСТР для полей и формат дат 'dd.mm.YYYY HH:MM:SS' для calendar.event.add, как того требует API.
    - Динамически получает и преобразует в int ID календаря.
    - Содержит полную обработку ошибок.
    """
    logging.info(f"Начало процесса бронирования. Преподаватель ID: {user_id}, Время: {start_time}")
    webhook_base_url = BITRIX24_WEBHOOK_URL.rstrip('/')
    end_time = start_time + timedelta(minutes=duration_minutes)

    async def make_b24_request(client, method, params):
        url = f"{webhook_base_url}/{method}"
        try:
            logging.debug(f"Запрос к Bitrix24. Метод: {method}, Параметры: {json.dumps(params, ensure_ascii=False, indent=2)}")
            response = await client.post(url, json=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP-ошибка {e.response.status_code} при вызове метода {method}. Ответ: {e.response.text}")
            return None
        except httpx.RequestError as e:
            logging.error(f"Критическая ошибка соединения при вызове метода {method}: {e}")
            return None

    try:
        async with httpx.AsyncClient(verify=False) as client:
            # Шаг 1: Проверка слота
            check_params = {'type': 'user', 'ownerId': user_id, 'from': start_time.isoformat(), 'to': end_time.isoformat()}
            check_data = await make_b24_request(client, 'calendar.event.get', check_params)
            if check_data and check_data.get('result'):
                logging.warning(f"Попытка двойного бронирования на {start_time} для user_id={user_id}. Слот уже занят.")
                return None, None

            # Шаг 2: Создание задачи
            user_info = await make_b24_request(client, 'user.get', {'ID': user_id})
            teacher_name = f"Преподаватель (ID: {user_id})"
            if user_info and user_info.get('result'):
                user = user_info['result'][0]
                teacher_name = f"{user.get('NAME', '')} {user.get('LAST_NAME', '')}".strip() or teacher_name
            
            child_name_gent = inflect_name(client_data.get('child_name', 'Клиент'), 'gent') if MORPHOLOGY_ENABLED else client_data.get('child_name', 'Клиент')
            task_description = (f"Новая заявка на пробный урок от @{client_data.get('username', 'N/A')}.\n\n"
                                f"Ученик: {client_data.get('child_name', 'не указано')}\n"
                                f"Преподаватель: [USER={user_id}]{teacher_name}[/USER]")

            task_params = {'fields': {
                'TITLE': f"Пробный урок для {child_name_gent} ({teacher_name})",
                'DESCRIPTION': task_description,
                'RESPONSIBLE_ID': user_id,
                'DEADLINE': start_time.isoformat(),
                'GROUP_ID': GROUP_ID
            }}
            
            task_data = await make_b24_request(client, 'tasks.task.add', task_params)
            if not (task_data and task_data.get('result') and task_data['result'].get('task')):
                logging.error(f"Не удалось создать задачу: {task_data}")
                return None, None
            task_id = task_data['result']['task']['id']
            logging.info(f"Задача (ID: {task_id}) успешно создана.")

            # Шаг 3: Динамическое получение ID календаря
            section_id = 1
            sections_data = await make_b24_request(client, 'calendar.section.get', {'type': 'user', 'ownerId': user_id})
            if sections_data and sections_data.get('result') and len(sections_data['result']) > 0:
                calendar_id_str = sections_data['result'][0].get('ID')
                if calendar_id_str:
                    section_id = int(calendar_id_str)
            
            # Шаг 4: Создание события
            event_description = (
                f"Запись из Telegram-бота.\n"
                f"Ученик: {client_data.get('child_name', 'не указано')}, {client_data.get('child_age', 'не указано')} лет.\n"
                f"Родитель: {client_data.get('parent_name', 'не указано')}.\n"
                f"Контакт: @{client_data.get('username', 'нет')}"
            )
            parsed_url = urlparse(webhook_base_url)
            portal_base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            task_url_bbcode = f"\n\nСвязанная задача: [URL={portal_base_url}/company/personal/user/{user_id}/tasks/task/view/{task_id}/]Задача №{task_id}[/URL]"
            final_event_description = event_description + task_url_bbcode
            event_params = {
                'type': 'user',
                'ownerId': str(user_id),
                'name': f"Пробный урок: {client_data.get('child_name', 'Клиент')}",
                # Это ссылка на привязанную к событию задачу
                'description': event_description + '\n' + final_event_description,
                'from': start_time.strftime('%d.%m.%Y %H:%M:%S'),
                'to': end_time.strftime('%d.%m.%Y %H:%M:%S'),
                'section': section_id,
                'accessibility': 'busy'
            }
            
            event_creation_response = await make_b24_request(client, 'calendar.event.add', event_params)
            if not event_creation_response or not event_creation_response.get('result'):
                logging.error(f"Не удалось создать событие в календаре. Ответ API: {event_creation_response}")
                return None, None

            logging.info(f"Событие в календаре (ID: {event_creation_response.get('result')}) успешно создано.")
            return task_id, teacher_name

    except Exception as e:
        logging.error(f"Непредвиденная критическая ошибка в функции book_lesson: {e}", exc_info=True)
        return None, None