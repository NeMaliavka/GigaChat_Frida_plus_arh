# app/services/bitrix_service.py
import asyncio
import httpx
import logging
from datetime import datetime, timedelta

# --- ИСПРАВЛЕНИЕ: Импортируем напрямую переменную из конфига ---
from app.config import BITRIX24_WEBHOOK_URL, TEACHER_IDS

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

# async def get_free_slots(from_date: datetime, to_date: datetime, user_ids: list[int]):
#     """
#     Получает список свободных временных слотов для указанных пользователей.
#     Использует метод calendar.accessibility.get
#     """
#     if not TEACHER_IDS:
#         logging.warning("Список ID учителей в конфиге пуст. Невозможно получить слоты.")
#         return None
#     api_method = "calendar.accessibility.get"
#     url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{api_method}"
    
#     params = {
#         'from': from_date.isoformat(),
#         'to': to_date.isoformat(),
#         'users': user_ids,
#     }

#     try:
#         async with httpx.AsyncClient(verify=False) as client:
#             response = await client.post(url, json=params)
#             response.raise_for_status()
#             data = response.json()
#             # Правильно проверяем, что в 'result' есть данные.
#             # 'result' может быть пустым списком [], и это нормально.
#             if 'result' in data and data['result']:
#                 logging.info(f"Получены слоты доступности для пользователей {TEACHER_IDS}")
#                 # Ответ API сразу содержит словарь доступности, без вложенности.
#                 return data['result']
#             else:
#                 # Если 'result' пустой или его нет - значит, слотов не найдено.
#                 # Это не ошибка, а штатная ситуация.
#                 logging.info("Свободные слоты не найдены для указанных пользователей и дат.")
#                 return {} # Возвращаем пустой словарь, а не None
#             # if 'result' in data and 'accessibility' in data['result']:
#             #     logging.info(f"Получены слоты доступности для пользователей {user_ids}")
#             #     return data['result']['accessibility']
#             # else:
#             #     logging.error(f"Ошибка при получении слотов: {data.get('error_description') or data}")
#             #     return None
#     except httpx.RequestError as e:
#         logging.error(f"Ошибка HTTP при запросе слотов: {e}")
#         return None
# НОВАЯ ВЕРСИЯ ФУНКЦИИ get_free_slots

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
                for event in data['result']:
                    start_busy = datetime.fromisoformat(event['DATE_FROM'])
                    end_busy = datetime.fromisoformat(event['DATE_TO'])
                    busy_intervals.append((start_busy, end_busy))

                portal_tz = from_date.tzinfo
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
    # try:
    #     async with httpx.AsyncClient(verify=False) as client:
    #         # Запрашиваем события для всех учителей одним махом
    #         params = {
    #             'type': 'user',
    #             'ownerId': user_ids[0], # Для простоты пока берем первого учителя
    #             'from': from_date.isoformat(),
    #             'to': to_date.isoformat(),
    #         }
    #         response = await client.post(url, json=params)
    #         response.raise_for_status()
    #         data = response.json()

    #         if 'result' not in data:
    #             logging.error(f"Ошибка API при получении событий: {data.get('error_description') or data}")
    #             return None

    #         # Собираем все занятые временные интервалы
    #         busy_intervals = []
    #         for event in data['result']:
    #             # Учитываем часовые пояса, которые возвращает API
    #             start_busy = datetime.fromisoformat(event['DATE_FROM'])
    #             end_busy = datetime.fromisoformat(event['DATE_TO'])
    #             busy_intervals.append((start_busy, end_busy))

    #         # Теперь вычисляем свободные слоты
    #         portal_tz = from_date.tzinfo
    #         current_day = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
            
    #         for day_offset in range((to_date - from_date).days + 1):
    #             check_day = current_day + timedelta(days=day_offset)
                
    #             # Пропускаем выходные, например, субботу (5) и воскресенье (6)
    #             if check_day.weekday() >= 5:
    #                 continue

    #             # Итерируемся по рабочим часам с шагом в `lesson_duration`
    #             for hour in range(work_hours['start'], work_hours['end']):
    #                 slot_start = check_day.replace(hour=hour, minute=0, tzinfo=portal_tz)
    #                 slot_end = slot_start + timedelta(minutes=lesson_duration)
                    
    #                 # Проверяем, чтобы слот не выходил за рамки рабочего дня
    #                 if slot_end.hour > work_hours['end']:
    #                     continue

    #                 # Проверяем, чтобы слот не был в прошлом
    #                 if slot_start < datetime.now(portal_tz):
    #                     continue

    #                 # Проверяем на пересечение с занятыми интервалами
    #                 is_free = True
    #                 for busy_start, busy_end in busy_intervals:
    #                     # Условие пересечения двух интервалов [A,B] и [C,D] -> A < D и C < B
    #                     if slot_start < busy_end and busy_start < slot_end:
    #                         is_free = False
    #                         break
                    
    #                 if is_free:
    #                     date_key = slot_start.strftime('%Y-%m-%d')
    #                     if date_key not in all_free_slots:
    #                         all_free_slots[user_ids[0]] = [] # Пока используем ID первого учителя
    #                         all_free_slots[date_key] = []

    #                     all_free_slots[date_key].append({
    #                         'time': slot_start.strftime('%H:%M'),
    #                         'user_id': user_ids[0]
    #                     })
            
    #         # Возвращаем результат в формате, который ожидает хендлер
    #         # {'user_id': [{'from': ..., 'to': ...}]} -> мы вернем наш аналог
    #         # {'date': [{'time': ..., 'user_id': ...}]}
    #         # Хендлер нужно будет немного адаптировать
    #         return all_free_slots

    # except httpx.RequestError as e:
    #     logging.error(f"Ошибка HTTP при запросе событий: {e}")
    #     return None

async def book_lesson(user_id: int, start_time: datetime, duration_minutes: int, client_data: dict):
    """
    Создает событие (бронирует урок) в календаре сотрудника.
    Использует метод calendar.event.add
    """
    api_method = "calendar.event.add"
    url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{api_method}"
    
    end_time = start_time + timedelta(minutes=duration_minutes)
    
    # Формируем красивое название и описание для события в Битрикс24
    event_name = f"Пробный урок для: {client_data.get('child_name', 'Клиент')}"
    event_description = (
        f"Запись из Telegram-бота.\n"
        f"Ученик: {client_data.get('child_name', 'не указано')}, {client_data.get('child_age', 'не указано')} лет.\n"
        f"Родитель: {client_data.get('parent_name', 'не указано')}.\n"
        f"Контакт: @{client_data.get('username', 'нет')}"
    )

    params = {
        'type': 'user',          # Тип календаря - пользовательский
        'ownerId': user_id,      # ID сотрудника (учителя), в чей календарь добавляем событие
        'name': event_name,      # Название события
        'description': event_description, # Описание
        'from': start_time.isoformat(),
        'to': end_time.isoformat(),
        'sect_id': 1, # ID секции календаря, обычно 1 это "Мой календарь"
        'remind': [{'type': 'min', 'count': 60}] # Напоминание за 60 минут
    }

    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(url, json=params)
            response.raise_for_status()
            data = response.json()

            if 'result' in data:
                event_id = data['result']
                logging.info(f"Урок успешно забронирован. ID события: {event_id}")
                return event_id
            else:
                logging.error(f"Ошибка при бронировании урока: {data.get('error_description') or data}")
                return None
    except httpx.RequestError as e:
        logging.error(f"Ошибка HTTP при бронировании урока: {e}")
        return None
