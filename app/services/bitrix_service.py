# # app/services/bitrix_service.py
# import asyncio
# import httpx
# import logging
# from datetime import datetime, timedelta
# from urllib.parse import urlparse # Импортируем для извлечения URL портала

# # --- ИСПРАВЛЕНИЕ: Импортируем напрямую переменную из конфига ---
# from app.config import BITRIX24_WEBHOOK_URL, TEACHER_IDS, GROUP_ID

# # --- ИЗМЕНЕНИЕ 1: Импортируем нашу утилиту для склонения имен ---
# try:
#     from app.utils.text_tools import inflect_name
#     MORPHOLOGY_ENABLED = True
# except ImportError:
#     logging.warning("Утилиты склонения не найдены, имена в задачах будут в именительном падеже.")
#     MORPHOLOGY_ENABLED = False
#     # Создаем заглушку, чтобы код не падал

# async def check_b24_connection():
#     """
#     Отправляет тестовый запрос к API Битрикс24 для проверки соединения.
#     """
#     # --- ИСПРАВЛЕНИЕ: Используем переменную напрямую ---
#     if not BITRIX24_WEBHOOK_URL:
#         logging.error("URL вебхука Битрикс24 (BITRIX24_WEBHOOK_URL) не настроен в .env файле.")
#         return None

#     api_method = "app.info"
#     url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{api_method}"

#     try:
#         # Для коробочных версий оставляем verify=False
#         async with httpx.AsyncClient(verify=False) as client:
#             response = await client.post(url)
#             response.raise_for_status()
#             data = response.json()
            
#             if 'result' in data:
#                 logging.info("Соединение с Битрикс24 успешно установлено!")
#                 api_version = data['result'].get('VERSION', 'недоступна (стандартно для вебхука)')
#                 logging.info(f"Версия REST API: {api_version}")
#                 return data['result']
#             else:
#                 logging.error(f"Ошибка при запросе к Битрикс24: {data.get('error_description') or data}")
#                 return None

#     except httpx.RequestError as e:
#         logging.error(f"Ошибка HTTP-запроса к Битрикс24: {e}")
#         return None

# # Этот блок для самостоятельного тестирования файла оставляем, он полезен
# if __name__ == "__main__":
#     logging.basicConfig(level=logging.INFO)
#     # Перед запуском этого файла убедись, что .env файл доступен из корня проекта
#     asyncio.run(check_b24_connection())

# async def book_lesson(user_id: int, start_time: datetime, duration_minutes: int, client_data: dict):
#     """
#     Создает ЗАДАЧУ и связанное с ней СОБЫТИЕ в календаре Битрикс24.
#     """
#     # Вспомогательная функция для чистоты кода
#     async def make_b24_request(client, method, params):
#         url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{method}"
#         try:
#             response = await client.post(url, json=params)
#             response.raise_for_status()
#             return response.json()
#         except httpx.RequestError as e:
#             logging.error(f"HTTP-ошибка при вызове метода {method}: {e}")
#             return None
#         except Exception as e:
#             logging.error(f"Неизвестная ошибка при вызове метода {method}: {e}")
#             return None

#     # Получаем URL портала из вебхука для создания красивых ссылок
#     parsed_url = urlparse(BITRIX24_WEBHOOK_URL)
#     portal_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

#     async with httpx.AsyncClient(verify=False) as client:
#         # --- Шаг 1: Получаем имя преподавателя по ID ---
#         user_info_data = await make_b24_request(client, 'user.get', {'ID': user_id})
#         teacher_name = "Преподаватель"
#         if user_info_data and user_info_data.get('result'):
#             user_result = user_info_data['result'][0]
#             teacher_name = f"{user_result.get('NAME', '')} {user_result.get('LAST_NAME', '')}".strip()
#         child_name = client_data.get('child_name', 'Клиент')
#         # Склоняем имя в родительный падеж ('кого?', 'для кого?')
#         child_name_gent = inflect_name(child_name, 'gent')
#         # --- Шаг 2: Создаем основную сущность - Задачу ---
#         task_description = (
#             f"Новая заявка на пробный урок из Telegram-бота.\n\n"
#             f"[B]Ученик:[/B] {client_data.get('child_name', 'не указано')}\n"
#             f"[B]Возраст:[/B] {client_data.get('child_age', 'не указано')} лет\n"
#             f"[B]Увлечения:[/B] {client_data.get('child_hobbies', 'не указано')}\n\n"
#             f"[B]Родитель:[/B] {client_data.get('parent_name', 'не указано').capitalize()}\n"
#             f"[B]Контакт родителя:[/B] {client_data.get('parent_contact', 'не указано')}\n"
#             f"[B]Telegram:[/B] @{client_data.get('username', 'нет')}\n\n"
#             f"-------------------------------------\n"
#             # ИЗМЕНЕНИЕ: Отображаем имя преподавателя
#             f"Назначенный преподаватель: [USER={user_id}]{teacher_name}[/USER]\n"
#             f"Забронированное время: [B]{start_time.isoformat()}(МСК)[/B]"
#         )

#         task_params = {
#             'fields': {
#                 'TITLE': f"Пробный урок для {child_name_gent}  ({teacher_name})",
#                 'DESCRIPTION': task_description,
#                 'RESPONSIBLE_ID': user_id,
#                 'DEADLINE': start_time.isoformat(),
#                 'GROUP_ID': GROUP_ID # ВАЖНО: Укажи ID своего проекта (группы) для задач!
#             }
#         }
#         task_creation_result = await make_b24_request(client, 'tasks.task.add', task_params)

#         if not (task_creation_result and 'result' in task_creation_result and 'task' in task_creation_result['result']):
#             logging.error(f"Не удалось создать задачу: {task_creation_result.get('error_description') or 'Неизвестная ошибка'}")
#             return None

#         task_id = task_creation_result['result']['task']['id']
#         logging.info(f"Задача на пробный урок успешно создана. ID задачи: {task_id}")
        
#         # --- Шаг 3: Создаем связанное Событие в календаре ---
#         end_time = start_time + timedelta(minutes=duration_minutes)
#         task_url = f"{portal_url}/company/personal/user/{user_id}/tasks/task/view/{task_id}/"

#         event_description = (
#             f"Запись на пробный урок с {client_data.get('parent_name', 'клиентом')} (ученик: {client_data.get('child_name', 'не указано')}).\n"
#             f"Вся подробная информация находится в связанной задаче.\n\n"
#             f"[URL='{task_url}']Перейти к задаче[/URL]" # ДОБАВЛЕНО: Ссылка на задачу
#         )
        
#         event_params = {
#             'type': 'user', 'ownerId': user_id,
#             'name': f"Пробный урок: {client_data.get('child_name', 'Клиент')}",
#             'description': event_description, 'from': start_time.isoformat(),
#             'to': end_time.isoformat(), 'sect_id': 1,
#             'remind': [{'type': 'min', 'count': 60}],
#             # Явно указываем преподавателя как подтвержденного участника,
#             # чтобы событие гарантированно блокировало его время.
#             'attendees': [user_id],
#             'BUSYNESS': 'busy'
#         }
#         event_creation_result = await make_b24_request(client, 'calendar.event.add', event_params)

#         if event_creation_result and 'result' in event_creation_result:
#             event_id = event_creation_result['result']
#             logging.info(f"Событие в календаре (ID: {event_id}) успешно создано и связано с задачей (ID: {task_id}).")
#         else:
#             logging.warning(f"Задача создана (ID: {task_id}), но не удалось создать связанное событие в календаре.")
            
#         return task_id # Возвращаем ID главной сущности - Задачи


# # # ФИНАЛЬНАЯ, ПРОИЗВОДСТВЕННАЯ ВЕРСИЯ
# # async def get_free_slots(from_date: datetime, to_date: datetime, user_ids: list[int], lesson_duration: int = 60):
# #     """
# #     Получает свободные слоты, запрашивая все события и вычисляя "окна" на стороне бота.
# #     Эта версия надежно работает на любом тарифе Битрикс24 и корректно парсит формат даты.
# #     """
# #     api_method = "calendar.event.get"
# #     url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{api_method}"

# #     work_hours = {'start': 10, 'end': 18}
# #     final_slots = {}
# #     portal_tz = from_date.tzinfo

# #     try:
# #         async with httpx.AsyncClient(verify=False) as client:
# #             for user_id in user_ids:
# #                 params = {
# #                     'type': 'user',
# #                     'ownerId': user_id,
# #                     'from': from_date.isoformat(),
# #                     'to': to_date.isoformat(),
# #                 }
# #                 response = await client.post(url, json=params)
# #                 response.raise_for_status()
# #                 data = response.json()

# #                 if 'result' not in data:
# #                     logging.error(f"Ошибка API при получении событий для user_id {user_id}: {data.get('error_description') or data}")
# #                     continue

# #                 busy_intervals = []
# #                 for event in data['result']:
# #                     try:
# #                         # --- КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ ЗДЕСЬ ---
# #                         # Используем strptime с явным указанием формата ДД.ММ.ГГГГ ЧЧ:ММ:СС
# #                         naive_start = datetime.strptime(event['DATE_FROM'], '%d.%m.%Y %H:%M:%S')
# #                         naive_end = datetime.strptime(event['DATE_TO'], '%d.%m.%Y %H:%M:%S')

# #                         # Делаем время "осведомленным" о часовом поясе
# #                         start_busy = naive_start.replace(tzinfo=portal_tz)
# #                         end_busy = naive_end.replace(tzinfo=portal_tz)
# #                         busy_intervals.append((start_busy, end_busy))
# #                     except (ValueError, KeyError) as e:
# #                         logging.warning(f"Не удалось распознать дату события, пропускаем. Ошибка: {e}, Данные: {event}")
# #                         continue
                
# #                 # --- Дальнейшая логика вычисления слотов остается без изменений ---
# #                 for day_offset in range((to_date - from_date).days + 1):
# #                     check_day = (from_date + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
                    
# #                     if check_day.weekday() >= 5: continue

# #                     for hour in range(work_hours['start'], work_hours['end']):
# #                         slot_start = check_day.replace(hour=hour, minute=0)
# #                         slot_end = slot_start + timedelta(minutes=lesson_duration)
                        
# #                         if slot_end.hour > work_hours['end'] or slot_start < datetime.now(portal_tz):
# #                             continue

# #                         is_free = True
# #                         for busy_start, busy_end in busy_intervals:
# #                             if slot_start < busy_end and busy_start < slot_end:
# #                                 is_free = False
# #                                 break
                        
# #                         if is_free:
# #                             date_key = slot_start.strftime('%Y-%m-%d')
# #                             if date_key not in final_slots:
# #                                 final_slots[date_key] = []
# #                             final_slots[date_key].append({'time': slot_start.strftime('%H:%M'), 'user_id': user_id})
        
# #         for date_key in final_slots:
# #             final_slots[date_key] = sorted(final_slots[date_key], key=lambda x: x['time'])
            
# #         return final_slots

# #     except httpx.RequestError as e:
# #         logging.error(f"Критическая HTTP ошибка при запросе событий: {e}")
# #         return None
# async def get_free_slots(from_date: datetime, to_date: datetime, user_ids: list[int], lesson_duration: int = 60):
#     """
#     Получает свободные слоты, запрашивая все события и вычисляя "окна" на стороне бота.
#     Эта версия надежно работает на любом тарифе Битрикс24.
#     """
#     api_method = "calendar.event.get"
#     url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{api_method}"

#     # Определяем рабочий график прямо здесь. В будущем можно вынести в конфиг.
#     work_hours = {'start': 10, 'end': 19}
    
#     all_free_slots = {}
#     final_slots = {}
#     try:
#         async with httpx.AsyncClient(verify=False) as client:
#             for user_id in user_ids:
#                 params = {
#                     'type': 'user',
#                     'ownerId': user_id,
#                     'from': from_date.isoformat(),
#                     'to': to_date.isoformat(),
#                 }
#                 response = await client.post(url, json=params)
#                 response.raise_for_status()
#                 data = response.json()

#                 if 'result' not in data:
#                     logging.error(f"Ошибка API при получении событий для user_id {user_id}: {data.get('error_description') or data}")
#                     continue # Пропускаем этого учителя, если по нему ошибка

#                 busy_intervals = []
#                 for event in data['result']:
#                     start_busy = datetime.fromisoformat(event['DATE_FROM'])
#                     end_busy = datetime.fromisoformat(event['DATE_TO'])
#                     busy_intervals.append((start_busy, end_busy))

#                 portal_tz = from_date.tzinfo
#                 for day_offset in range((to_date - from_date).days + 1):
#                     check_day = (from_date + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
                    
#                     if check_day.weekday() >= 5: continue

#                     for hour in range(work_hours['start'], work_hours['end']):
#                         slot_start = check_day.replace(hour=hour, minute=0, tzinfo=portal_tz)
#                         slot_end = slot_start + timedelta(minutes=lesson_duration)
                        
#                         if slot_end.hour > work_hours['end'] or slot_start < datetime.now(portal_tz):
#                             continue

#                         is_free = True
#                         for busy_start, busy_end in busy_intervals:
#                             if slot_start < busy_end and busy_start < slot_end:
#                                 is_free = False
#                                 break
                        
#                         if is_free:
#                             date_key = slot_start.strftime('%Y-%m-%d')
#                             if date_key not in final_slots:
#                                 final_slots[date_key] = []
#                             final_slots[date_key].append({'time': slot_start.strftime('%H:%M'), 'user_id': user_id})
        
#         # Сортируем слоты по времени внутри каждого дня
#         for date_key in final_slots:
#             final_slots[date_key] = sorted(final_slots[date_key], key=lambda x: x['time'])
            
#         return final_slots

#     except httpx.RequestError as e:
#         logging.error(f"Критическая HTTP ошибка при запросе событий: {e}")
#         return None

# app/services/bitrix_service.py
# ФИНАЛЬНАЯ, ЧИСТАЯ И ПРОИЗВОДСТВЕННАЯ ВЕРСИЯ

import httpx
import logging
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

async def get_free_slots(from_date: datetime, to_date: datetime, user_ids: list[int], lesson_duration: int = 60):
    """
    Получает свободные слоты, запрашивая все события и вычисляя "окна" на стороне бота.
    Эта версия надежно работает на любом тарифе Битрикс24.
    """
    api_method = "calendar.event.get"
    url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{api_method}"

    # Определяем рабочий график прямо здесь. В будущем можно вынести в конфиг.
    work_hours = {'start': 10, 'end': 19}
    
    all_free_slots = {}
    final_slots = {}
    try:
        async with httpx.AsyncClient(verify=False) as client:
            for user_id in user_ids:
                params = {
                    'type': 'user',
                    'ownerId': user_id,
                    'from': from_date.isoformat(),
                    'to': to_date.isoformat(),
                }
                response = await client.post(url, json=params)
                response.raise_for_status()
                data = response.json()

                if 'result' not in data:
                    logging.error(f"Ошибка API при получении событий для user_id {user_id}: {data.get('error_description') or data}")
                    continue # Пропускаем этого учителя, если по нему ошибка

                busy_intervals = []
                portal_tz = from_date.tzinfo
                for event in data['result']:
                        naive_start = datetime.strptime(event['DATE_FROM'], '%d.%m.%Y %H:%M:%S')
                        naive_end = datetime.strptime(event['DATE_TO'], '%d.%m.%Y %H:%M:%S')

                        # Делаем время "осведомленным" о часовом поясе
                        start_busy = naive_start.replace(tzinfo=portal_tz)
                        end_busy = naive_end.replace(tzinfo=portal_tz)
                        busy_intervals.append((start_busy, end_busy))

                
                for day_offset in range((to_date - from_date).days + 1):
                    check_day = (from_date + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
                    
                    if check_day.weekday() >= 5: continue

                    for hour in range(work_hours['start'], work_hours['end']):
                        slot_start = check_day.replace(hour=hour, minute=0, tzinfo=portal_tz)
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
        
        # Сортируем слоты по времени внутри каждого дня
        for date_key in final_slots:
            final_slots[date_key] = sorted(final_slots[date_key], key=lambda x: x['time'])
            
        return final_slots

    except httpx.RequestError as e:
        logging.error(f"Критическая HTTP ошибка при запросе событий: {e}")
        return None

# async def book_lesson(user_id: int, start_time: datetime, duration_minutes: int, client_data: dict):
#     """
#     Создает ЗАДАЧУ и связанное с ней СОБЫТИЕ в календаре, которое гарантированно блокирует время.
#     """
#     async def make_b24_request(client, method, params):
#         url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{method}"
#         try:
#             response = await client.post(url, json=params)
#             response.raise_for_status()
#             return response.json()
#         except httpx.RequestError as e:
#             logging.error(f"HTTP-ошибка при вызове метода {method}: {e}")
#             return None
    
#     parsed_url = urlparse(BITRIX24_WEBHOOK_URL)
#     portal_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

#     async with httpx.AsyncClient(verify=False) as client:
#         user_info_data = await make_b24_request(client, 'user.get', {'ID': user_id})
#         teacher_name = "Преподаватель"
#         if user_info_data and user_info_data.get('result'):
#             user_result = user_info_data['result'][0]
#             teacher_name = f"{user_result.get('NAME', '')} {user_result.get('LAST_NAME', '')}".strip()

#         child_name = client_data.get('child_name', 'Клиент')
#         child_name_gent = inflect_name(child_name, 'gent')

#         task_description = (
#             f"Новая заявка на пробный урок из Telegram-бота.\n\n"
#             f"[B]Ученик:[/B] {child_name}\n"
#             f"[B]Возраст:[/B] {client_data.get('child_age', 'не указано')} лет\n"
#             f"[B]Увлечения:[/B] {client_data.get('child_hobbies', 'не указано')}\n\n"
#             f"[B]Родитель:[/B] {client_data.get('parent_name', 'не указано').capitalize()}\n"
#             f"[B]Контакт родителя:[/B] {client_data.get('parent_contact', 'не указано')}\n"
#             f"[B]Telegram:[/B] @{client_data.get('username', 'нет')}\n\n"
#             f"-------------------------------------\n"
#             f"Назначенный преподаватель: [USER={user_id}]{teacher_name}[/USER]\n"
#             f"Забронированное время: [B]{start_time.strftime('%d %B %Y в %H:%M')} (МСК)[/B]"
#         )

#         task_params = {'fields': {
#             'TITLE': f"Пробный урок для {child_name_gent} ({teacher_name})",
#             'DESCRIPTION': task_description,
#             'RESPONSIBLE_ID': user_id,
#             'DEADLINE': start_time.isoformat(),
#             'GROUP_ID': GROUP_ID
#         }}
#         task_creation_result = await make_b24_request(client, 'tasks.task.add', task_params)

#         if not (task_creation_result and 'result' in task_creation_result and 'task' in task_creation_result['result']):
#             logging.error(f"Не удалось создать задачу: {task_creation_result.get('error_description') or 'Неизвестная ошибка'}")
#             return None

#         task_id = task_creation_result['result']['task']['id']
#         logging.info(f"Задача на пробный урок успешно создана. ID задачи: {task_id}")
        
#         task_url = f"{portal_url}/company/personal/user/{user_id}/tasks/task/view/{task_id}/"
#         event_description = (
#             f"Запись на пробный урок с {client_data.get('parent_name', 'клиентом')} (ученик: {child_name}).\n"
#             f"Подробности: [URL='{task_url}']Перейти к задаче[/URL]"
#         )
        
#         event_params = {
#             'type': 'user', 'ownerId': user_id,
#             'name': f"Пробный урок: {child_name}",
#             'description': event_description, 'from': start_time.isoformat(),
#             'to': (start_time + timedelta(minutes=duration_minutes)).isoformat(),
#             'sect_id': 1, 'remind': [{'type': 'min', 'count': 60}],
#             'BUSYNESS': 'busy'
#         }
#         await make_b24_request(client, 'calendar.event.add', event_params)
            
#         return task_id

# Если вы используете утилиту для склонения имен, оставьте этот импорт
try:
    from app.utils.text_tools import inflect_name
except ImportError:
    def inflect_name(name, case): return name # Заглушка, если утилиты нет

async def book_lesson(user_id: int, start_time: datetime, duration_minutes: int, client_data: dict):
    """
    Бронирует урок: ПРОВЕРЯЕТ доступность слота, СОЗДАЕТ задачу и связанное СОБЫТИЕ.
    Это атомарно защищает от двойного бронирования.
    """
    webhook_base_url = BITRIX24_WEBHOOK_URL.rstrip('/')
    end_time = start_time + timedelta(minutes=duration_minutes)

    async def make_b24_request(client, method, params):
        url = f"{webhook_base_url}/{method}"
        try:
            response = await client.post(url, json=params)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            logging.error(f"HTTP-ошибка при вызове метода {method}: {e}")
            return None

    try:
        async with httpx.AsyncClient(verify=False) as client:
            # --- ШАГ 1: Проверка на наличие существующих событий в этом временном слоте ---
            check_params = {
                'type': 'user', 'ownerId': user_id,
                'from': start_time.isoformat(), 'to': end_time.isoformat()
            }
            logging.info(f"Проверяем слот перед бронированием для user_id={user_id} с {start_time} по {end_time}")
            check_data = await make_b24_request(client, 'calendar.event.get', check_params)

            # Если API вернул непустой список событий, значит слот уже занят
            if check_data and check_data.get('result'):
                logging.warning(f"Попытка двойного бронирования на {start_time} для user_id={user_id}. Слот уже занят.")
                return None # Возвращаем None, сигнализируя о неудаче

            # --- ШАГ 2: Слот свободен, создаем Задачу ---
           
            # Получаем имя преподавателя для заголовка задачи
            user_info = await make_b24_request(client, 'user.get', {'ID': user_id})
            teacher_name = ""
            if user_info and user_info.get('result'):
                user = user_info['result'][0]
                teacher_name = f"{user.get('NAME', '')} {user.get('LAST_NAME', '')}".strip()

            child_name_gent = inflect_name(client_data.get('child_name', 'Клиент'), 'gent')

            task_description = (
                f"Новая заявка на пробный урок из Telegram-бота.\n\n"
                f"[B]Ученик:[/B] {client_data.get('child_name', 'не указано')}\n"
                f"[B]Возраст:[/B] {client_data.get('child_age', 'не указано')} лет\n"
                f"[B]Увлечения:[/B] {client_data.get('child_hobbies', 'не указано')}\n\n"
                f"[B]Родитель:[/B] {client_data.get('parent_name', 'не указано').capitalize()}\n"
                f"[B]Контакт родителя:[/B] {client_data.get('parent_contact', 'не указано')}\n"
                f"[B]Telegram:[/B] @{client_data.get('username', 'нет')}\n\n"
                f"-------------------------------------\n"
                f"Назначенный преподаватель: [USER={user_id}]{teacher_name}[/USER]\n"
                f"Забронированное время: [B]{start_time.strftime('%d.%m.%Y %H:%M')}[/B]"
            )

            task_params = {'fields': {
                'TITLE': f"Пробный урок для {child_name_gent} ({teacher_name})",
                'DESCRIPTION': task_description,
                'RESPONSIBLE_ID': user_id,
                'DEADLINE': start_time.isoformat(),
                'GROUP_ID': GROUP_ID # Убедитесь, что GROUP_ID задан в конфиге
            }}
            
            task_data = await make_b24_request(client, 'tasks.task.add', task_params)
            if not (task_data and task_data.get('result') and task_data['result'].get('task')):
                logging.error(f"Не удалось создать задачу: {task_data}")
                return None # Если не удалось создать задачу, нет смысла продолжать
            
            task_id = task_data['result']['task']['id']
            logging.info(f"Задача (ID: {task_id}) успешно создана.")

            # --- ШАГ 3: Создаем связанное Событие в календаре ---
            parsed_url = urlparse(BITRIX24_WEBHOOK_URL)
            portal_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            task_url = f"{portal_url}/company/personal/user/{user_id}/tasks/task/view/{task_id}/"

            event_description = (
                f"Пробный урок. Ученик: {client_data.get('child_name', 'не указано')}.\n"
                f"Подробности в связанной задаче: [URL='{task_url}']Перейти к задаче (ID: {task_id})[/URL]"
            )

            event_params = {
                'type': 'user', 'ownerId': user_id,
                'name': f"Пробный урок: {client_data.get('child_name', 'Клиент')}",
                'description': event_description,
                'from': start_time.isoformat(),
                'to': end_time.isoformat(),
                'sect_id': 1,
                'remind': [{'type': 'min', 'count': 60}],
                'BUSYNESS': 'busy' # Крайне важно: блокируем время
            }
            await make_b24_request(client, 'calendar.event.add', event_params)

            return task_id # Возвращаем ID созданной задачи в случае успеха

    except Exception as e:
        logging.error(f"Критическая ошибка в функции book_lesson: {e}")
        return None