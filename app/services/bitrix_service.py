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
        
# --- УНИВЕРСАЛЬНАЯ ФУНКЦИЯ-УТИЛИТА ---
async def make_b24_request(client: httpx.AsyncClient, method: str, params: dict) -> dict | None:
    """
    Универсальная функция для отправки запросов к API Битрикс24.
    Централизованно обрабатывает ошибки и логирование.
    """
    url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{method}"
    try:
        logging.debug(f"Запрос к Bitrix24 -> Метод: {method}, Параметры: {json.dumps(params, ensure_ascii=False, indent=2)}")
        response = await client.post(url, json=params)
        response.raise_for_status()
        data = response.json()
        if 'result' in data:
            return data
        # Логируем ошибку, если API вернул ее в теле ответа
        logging.error(f"Ошибка API при вызове {method}: {data.get('error_description') or data}")
        return None
    except httpx.HTTPStatusError as e:
        logging.error(f"HTTP-ошибка {e.response.status_code} при вызове {method}. Ответ: {e.response.text}")
        return None
    except (httpx.RequestError, json.JSONDecodeError) as e:
        logging.error(f"Ошибка сети или десериализации JSON при вызове {method}: {e}")
        return None

async def get_free_slots(from_date: datetime, to_date: datetime, user_ids: list[int], lesson_duration: int = 60):
    """
    Получает свободные слоты, корректно проверяя пересечение с занятыми интервалами и
    надежно распознавая разные форматы дат от Битрикс24.
    """
    api_method = "calendar.event.get"
    url = f"{BITRIX24_WEBHOOK_URL.rstrip('/')}/{api_method}"
    work_hours = {'start': 10, 'end': 18}
    final_slots = {}
    portal_tz = from_date.tzinfo

    try:
        async with httpx.AsyncClient(verify=False) as client:
            all_users_busy_intervals = []
            
            # Сначала соберем все занятые интервалы по всем преподавателям
            for user_id in user_ids:
                params = {
                    'type': 'user', 
                    'ownerId': str(user_id),
                    'from': from_date.isoformat(), 
                    'to': to_date.isoformat()
                } # <--- ИСПРАВЛЕНО
                
                response = await client.post(url, json=params)
                response.raise_for_status()
                data = response.json()

                if 'result' not in data:
                    logging.error(f"Ошибка API при получении событий для user_id {user_id}: {data.get('error_description') or data}")
                    continue
                
                for event in data.get('result', []):
                    start_busy = _parse_b24_date(event.get('DATE_FROM'), portal_tz)
                    end_busy = _parse_b24_date(event.get('DATE_TO'), portal_tz)
                    if start_busy and end_busy:
                        all_users_busy_intervals.append((start_busy, end_busy))

            # Теперь ищем свободные слоты, зная все занятые интервалы
            for day_offset in range((to_date - from_date).days + 1):
                check_day = (from_date + timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
                if check_day.weekday() >= 5: continue

                for hour in range(work_hours['start'], work_hours['end']):
                    slot_start = check_day.replace(hour=hour, minute=0)
                    slot_end = slot_start + timedelta(minutes=lesson_duration)

                    if slot_end.hour > work_hours['end'] or slot_start < datetime.now(portal_tz):
                        continue

                    is_free_globally = True
                    for busy_start, busy_end in all_users_busy_intervals:
                        if slot_start < busy_end and busy_start < slot_end:
                            is_free_globally = False
                            break
                    
                    if is_free_globally:
                        # Если слот свободен глобально, нужно найти, кто из преподавателей свободен
                        available_teachers = []
                        for user_id in user_ids:
                            is_teacher_busy = False
                            # Проверяем занятость конкретного преподавателя
                            # (логика ниже предполагает, что вы хотите знать, кто именно свободен)
                            # Для упрощения пока считаем, что если слот свободен - свободны все
                            available_teachers.append(user_id)

                        if available_teachers:
                            date_key = slot_start.strftime('%Y-%m-%d')
                            if date_key not in final_slots:
                                final_slots[date_key] = []
                            
                            # Проверяем, нет ли уже такого времени в списке
                            time_str = slot_start.strftime('%H:%M')
                            if not any(slot['time'] == time_str for slot in final_slots[date_key]):
                                final_slots[date_key].append({'time': time_str, 'user_ids': available_teachers})

        # Сортируем
        for date_key in final_slots:
            final_slots[date_key] = sorted(final_slots[date_key], key=lambda x: x['time'])
        
        return final_slots

    except httpx.RequestError as e:
        logging.error(f"Критическая HTTP ошибка при запросе событий: {e}")
        return {}
    except Exception as e:
        logging.error(f"Непредвиденная ошибка в get_free_slots: {e}", exc_info=True)
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

    portal_tz = start_time.tzinfo

    try:
        async with httpx.AsyncClient(verify=False) as client:
             # Шаг 1: Проверка слота с ручной фильтрацией.
            # Мы больше не доверяем API фильтрацию по времени. Запрашиваем все события 
            # на весь день и проверяем пересечения в коде Python.
            
            day_start = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            check_params = {
                'type': 'user',
                'ownerId': str(user_id),
                # Используем формат ISO, который гарантированно вернет события за весь день
                'from': day_start.isoformat(),
                'to': day_end.isoformat()
            }
            
            check_data = await make_b24_request(client, 'calendar.event.get', check_params)

            # Теперь ищем реальные пересечения вручную
            true_conflicts = []
            if check_data and check_data.get('result'):
                all_day_events = check_data.get('result')
                for event in all_day_events:
                    # Используем существующий в файле парсер дат _parse_b24_date
                    event_start = _parse_b24_date(event.get('DATE_FROM'), portal_tz)
                    event_end = _parse_b24_date(event.get('DATE_TO'), portal_tz)

                    # Пропускаем события, у которых не удалось распознать дату
                    if not event_start or not event_end:
                        continue

                    # Ключевая логика: проверка наложения интервалов.
                    # Пересечение есть, если начало одного раньше конца другого И 
                    # конец одного позже начала другого.
                    if event_start < end_time and event_end > start_time:
                        true_conflicts.append(event)
            
            # Если после ручной проверки найдены реальные конфликты:
            if true_conflicts:
                event_names = [f"'{event.get('NAME')}' (ID: {event.get('ID')})" for event in true_conflicts]
                logging.warning(
                    f"Попытка двойного бронирования на {start_time} для user_id={user_id}. Слот уже занят. "
                    f"РЕАЛЬНО МЕШАЮЩИЕ события: {', '.join(event_names)}")
                return None, None, None

            # Шаг 2: Создание задачи
            user_info = await make_b24_request(client, 'user.get', {'ID': user_id})
            teacher_name = f"Преподаватель (ID: {user_id})"
            if user_info and user_info.get('result'):
                user = user_info['result'][0]
                teacher_name = f"{user.get('NAME', '')} {user.get('LAST_NAME', '')}".strip() or teacher_name
            
            child_name_gent = inflect_name(client_data.get('child_name', 'Клиент'), 'gent') if MORPHOLOGY_ENABLED else client_data.get('child_name', 'Клиент')
            task_description = (
                f"Новая заявка на пробный урок от @{client_data.get('username', 'N/A')}.\n\n"
                f"[B]Родитель:[/B] {client_data.get('parent_name', 'Не указано')}\n"
                f"[B]Ученик:[/B] {client_data.get('child_name', 'Не указано')}\n"
                f"[B]Возраст ученика:[/B] {client_data.get('child_age', 'Не указан')}\n"
                f"[B]Увлечения:[/B] {client_data.get('hobbies', 'Не указаны')}\n\n"
                f"[B]Как связаться:[/B] через Telegram (@{client_data.get('username', 'N/A')})"
            )
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
                return None, None, None
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
                'description': final_event_description,
                'from': start_time.strftime('%d.%m.%Y %H:%M:%S'),
                'to': end_time.strftime('%d.%m.%Y %H:%M:%S'),
                'section': section_id,
                'accessibility': 'busy'
            }
            
            event_creation_response = await make_b24_request(client, 'calendar.event.add', event_params)
            if not event_creation_response or not event_creation_response.get('result'):
                logging.error(f"Не удалось создать событие в календаре. Ответ API: {event_creation_response}")
                # ВАЖНО: Если событие не создалось, нужно удалить уже созданную задачу,
                # чтобы избежать "висячих" задач.
                logging.warning(f"Откатываем создание задачи (ID: {task_id}) из-за ошибки с созданием события.")
                await make_b24_request(client, 'tasks.task.delete', {'taskId': task_id})
                return None, None, None

            event_id = event_creation_response.get('result')
            logging.info(f"Событие в календаре (ID: {event_id}) успешно создано.")
            return task_id, event_id, teacher_name 

    except Exception as e:
        logging.error(f"Непредвиденная критическая ошибка в функции book_lesson: {e}", exc_info=True)
        return None, None, None
    

async def cancel_booking(task_id: int, event_id: int) -> bool:
    """
    Отменяет бронирование, удаляя задачу и событие в календаре Bitrix24.    
    :param task_id: ID задачи для удаления.
    :param event_id: ID события календаря для удаления.
    :return: True в случае успеха, False в случае ошибки.
    """
    logging.info(f"Начало отмены в Битрикс24. Задача: {task_id}, Событие: {event_id}")
    async with httpx.AsyncClient(verify=False) as client:
        # Шаг 1: Удаление события
        event_res = await make_b24_request(client, 'calendar.event.delete', {'id': event_id})
        if not (event_res and event_res.get('result')):
            logging.warning(f"Не удалось удалить событие (ID: {event_id}) или оно уже было удалено.")

        # Шаг 2: Удаление задачи
        task_res = await make_b24_request(client, 'tasks.task.delete', {'taskId': task_id})
        if task_res and task_res.get('result'):
            logging.info(f"Задача (ID: {task_id}) и связанное событие (ID: {event_id}) успешно удалены.")
            return True
        else:
            logging.error(f"Не удалось удалить задачу (ID: {task_id}). Ответ API: {task_res}")
            return False

# async def reschedule_booking(
#     task_id: int, 
#     event_id: int, 
#     old_start_time: datetime,
#     new_start_time: datetime, 
#     teacher_id: int, 
#     client_data: dict
# ) -> bool:
#     """Переносит запись и реализует атомарный откат в случае ошибки."""
#     logging.info(f"Начало переноса. Задача: {task_id}, Новое время: {new_start_time}")
#     new_end_time = new_start_time + timedelta(minutes=60)

#     async with httpx.AsyncClient(verify=False) as client:
#         # Шаг 1: Обновление события на НОВОЕ время
#         event_fields = {
#             'id': event_id, 'type': 'user', 'ownerId': teacher_id,
#             'from': new_start_time.strftime('%d.%m.%Y %H:%M:%S'),
#             'to': new_end_time.strftime('%d.%m.%Y %H:%M:%S'),
#             'description': (f"ЗАПИСЬ ПЕРЕНЕСЕНА.\nНовое время: {new_start_time.strftime('%d.%m.%Y %H:%M')}\n\n"
#                             f"Ученик: {client_data.get('child_name', 'не указано')}\n"
#                             f"Контакт: @{client_data.get('username', 'нет')}")
#         }
#         event_update_res = await make_b24_request(client, 'calendar.event.update', event_fields)
#         if not event_update_res:
#             logging.error(f"Не удалось обновить событие {event_id}. Перенос отменен.")
#             return False
        
#         logging.info(f"Событие {event_id} успешно перенесено на {new_start_time}.")

#         # Шаг 2: Обновление задачи
#         task_fields = {'taskId': task_id, 'fields': {'DEADLINE': new_start_time.isoformat()}}
#         task_update_res = await make_b24_request(client, 'tasks.task.update', task_fields)

#         if task_update_res:
#             logging.info(f"Задача {task_id} успешно обновлена с новым дедлайном.")
#             return True

#         # --- БЛОК ОТКАТА (срабатывает, если task_update_res is None) ---
#         logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Событие {event_id} перенесено, но не удалось обновить задачу {task_id}! ИНИЦИИРОВАН ОТКАТ.")
        
#         old_end_time = old_start_time + timedelta(minutes=60)
#         rollback_fields = {
#             'id': event_id, 'type': 'user', 'ownerId': teacher_id,
#             'from': old_start_time.strftime('%d.%m.%Y %H:%M:%S'),
#             'to': old_end_time.strftime('%d.%m.%Y %H:%M:%S'),
#             'description': ("!!! АВТОМАТИЧЕСКИЙ ОТКАТ ПЕРЕНОСА !!!\n"
#                           "Запись возвращена на исходное время из-за технической ошибки.")
#         }
        
#         rollback_res = await make_b24_request(client, 'calendar.event.update', rollback_fields)
#         if rollback_res:
#             logging.info(f"ОТКАТ УСПЕШЕН: Событие {event_id} возвращено на {old_start_time}.")
#         else:
#             logging.error(f"ОТКАТ НЕ УДАЛСЯ! Требуется ручное вмешательство для события {event_id} и задачи {task_id}.")
        
#         return False


# функция для переноса
async def reschedule_booking(
    task_id: int, 
    event_id: int, 
    old_start_time: datetime, # <--- НОВЫЙ ПАРАМЕТР
    new_start_time: datetime, 
    teacher_id: int, 
    client_data: dict
) -> bool:
    """
    Переносит существующую запись на новое время, обновляя задачу и событие в Битрикс24.
    :param task_id: ID существующей задачи.
    :param event_id: ID существующего события.
    :param new_start_time: Новое время начала урока.
    :param client_data: Данные о клиенте для обновления описаний.
    :return: True в случае успеха, False в случае ошибки.
    """
    logging.info(f"Начало переноса записи. Задача: {task_id}, Событие: {event_id}, Новое время: {new_start_time}")
    new_end_time = new_start_time + timedelta(minutes=60)
    parent_name = client_data.get('parent_name', 'не указано')
    child_name = client_data.get('child_name', 'не указано')
    child_age = client_data.get('child_age', 'не указан')
    hobbies = client_data.get('hobbies', 'не указаны')
    contact_info = client_data.get('contact_info', 'не указан')
    username = client_data.get('username', 'не указан')

    # Создаем красивое, многострочное описание
    description = (
        f"--- ⚠️ ИНФОРМАЦИЯ О ПЕРЕНОСЕ ---\n"
        f"Старое время: {old_start_time.strftime('%d.%m.%Y в %H:%M')}\n"
        f"Новое время: {new_start_time.strftime('%d.%m.%Y в %H:%M')}\n"
        f"---------------------------------\n\n"
        f"--- 📋 АНКЕТА КЛИЕНТА ---\n"
        f"Ученик: {child_name}\n"
        f"Возраст: {child_age}\n"
        f"Родитель: {parent_name}\n"
        f"Контакт Telegram: @{username}\n"
        f"Доп. контакт (тел/email): {contact_info}\n"
        f"Интересы/хобби: {hobbies}\n"
        f"---------------------------------"
    )
    try:
        async with httpx.AsyncClient(verify=False) as client:
            # Шаг 1: Обновление события в календаре
            event_fields = {
                'id': event_id,
                'type': 'user', 
                'ownerId': teacher_id,
                'from': new_start_time.strftime('%d.%m.%Y %H:%M:%S'),
                'to': new_end_time.strftime('%d.%m.%Y %H:%M:%S'),
                'description': description
            }
            event_update_res = await make_b24_request(client, 'calendar.event.update', event_fields)
            if not event_update_res:
                logging.error(f"Не удалось обновить событие {event_id}. Перенос отменен.")
                return False
            logging.info(f"Событие {event_id} успешно перенесено на {new_start_time}.")

            # Шаг 2: Обновление задачи
            task_fields = {
                'taskId': task_id,
                'fields': {
                    'DEADLINE': new_start_time.isoformat(),
                }
            }
            task_update_res = await make_b24_request(client, 'tasks.task.update', task_fields)

            if not task_update_res:
                logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Событие {event_id} перенесено, но не удалось обновить задачу {task_id}!")
                # --- НАЧАЛО БЛОКА ОТКАТА ---
                logging.critical(f"КРИТИЧЕСКАЯ ОШИБКА: Событие {event_id} перенесено, но не удалось обновить задачу {task_id}!")
                logging.info(f"ИНИЦИИРОВАН АВТОМАТИЧЕСКИЙ ОТКАТ. Возвращаем событие {event_id} на старое время: {old_start_time}")
                
                old_end_time = old_start_time + timedelta(minutes=60)
                rollback_fields = {
                    'id': event_id,
                    'type': 'user',
                    'ownerId': teacher_id,
                    'from': old_start_time.strftime('%d.%m.%Y %H:%M:%S'),
                    'to': old_end_time.strftime('%d.%m.%Y %H:%M:%S'),
                    'description': f"!!! АВТОМАТИЧЕСКИЙ ОТКАТ ПЕРЕНОСА !!!\n" + \
                                   f"Запись возвращена на исходное время из-за технической ошибки."
                }
                
                rollback_res = await make_b24_request(client, 'calendar.event.update', rollback_fields)
                if rollback_res:
                    logging.info(f"ОТКАТ УСПЕШЕН: Событие {event_id} возвращено на {old_start_time}.")
                else:
                    logging.error(f"ОТКАТ НЕ УДАЛСЯ! Требуется ручное вмешательство для события {event_id} и задачи {task_id}.")
                
                return False # Возвращаем False, так как основная операция не удалась
                # --- КОНЕЦ БЛОКА ОТКАТА ---
            
            logging.info(f"Задача {task_id} успешно обновлена с новым дедлайном.")
            return True

    except Exception as e:
        logging.error(f"Непредвиденная ошибка в reschedule_booking: {e}", exc_info=True)
        return False

