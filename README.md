AI-Менеджер для Telegram: Полная Документация
1. Введение: Философия проекта
Добро пожаловать в документацию по универсальному AI-менеджеру для Telegram! Это не просто чат-бот, а полноценная платформа для создания проактивных, эмпатичных и продающих цифровых сотрудников.

Ключевая философия проекта — полное и бескомпромиссное разделение Кода (Движка) и Знаний (Конфигурации).

Представьте, что мы создали идеальный автомобильный двигатель (/app). Он мощный, надежный и универсальный. А вы, как владелец, можете поставить этот двигатель в любой кузов (/knowledge_base) — будь то спортивный автомобиль, семейный минивэн или внедорожник. Вы меняете внешний вид, салон и даже правила дорожного движения, по которым он едет, не залезая внутрь самого двигателя.

Это позволяет любому человеку, даже без навыков программирования, полностью изменить личность, сценарии и бизнес-логику бота, просто отредактировав несколько текстовых файлов.

2. 🏛️ Архитектура проекта: Как устроен наш «Автомобиль»
Проект состоит из четко разделенных модулей, каждый из которых выполняет свою уникальную роль.

/nobugs_bot

├── .env                  # Сейф с секретными ключами (API-токены, вебхуки и т.д.)

├── Dockerfile            # Инструкция для сборки "коробки" с нашим ботом

├── docker-compose.yml    # Инструкция для запуска бота и базы данных вместе

├── requirements.txt      # Список "запчастей" (библиотек), необходимых для работы

└── /app                  # Сам "Двигатель" - ядро нашего бота

    ├── main.py           # 🚀 "Ключ зажигания" - главный файл для запуска

    ├── config.py         # "Приборная панель" - загружает все настройки из .env
    
    |

    ├── /core             # 🧠 "Бортовой компьютер" (Мозг) - здесь вся интеллектуальная логика

    │   ├── llm_service.py         # 📞 "Телефонная линия" для связи с главным AI (GigaChat)

    │   ├── template_service.py    # 📚 "Книга быстрых ответов" (шпаргалка)

    │   ├── business_logic.py      # ⚖️ "Юридический отдел" - принимает решения по правилам

    │   └── admin_notifications.py # 🚨 "Тревожная кнопка" для вызова администратора

    |

    ├── /handlers         # 🗣️ "Уши и Рот" - прием и отправка сообщений, управление сценариями

    │   ├── sales_funnel.py        # 🤵 Главный "Менеджер зала" - решает, что делать с сообщением

    │   ├── onboarding_handlers.py # 👋 "Анкетолог" - проводит знакомство с новым клиентом

    │   ├── booking_handlers.py    # 📅 "Администратор записи" - управляет календарем и бронью

    │   └── cancellation_handlers.py # 🚫 "Отдел отмены" - обрабатывает отмену записи

    |

    ├── /b24              # 🔗 "Мост к Bitrix24" - все функции для работы с CRM

    │   ├── bitrix_service.py      # Функции для получения слотов и создания брони

    │   └── bitrix_cancel_service.py # Функции для отмены и удаления брони

    |

    ├── /db               # 💾 "Память" - все, что связано с хранением информации

    │   ├── models.py              # 📝 "Чертежи" базы данных - как выглядят таблицы

    │   └── database.py            # 👷 "Строитель" - умеет записывать и читать из БД

    |

    ├── /states           # 📌 "Состояния" - определяет шаги для многошаговых сценариев (FSM)

    │   └── fsm_states.py

    |

    └── /knowledge_base   # ❤️ "Душа и Характер" - настраиваемая часть бота

        ├── /documents/            # 🗄️ "Архив"

        │   ├── project_info.pdf   # Фундаментальные знания (прайс-лист, описание услуг)

        │   ├── lor.txt            # "Паспорт" AI - его личность, характер и правила

        │   └── templates.py       # "Блокнот" с готовыми фразами для быстрых ответов

        ├── /scenarios/

        │   └── fsm_scenario.json  # 📋 "Анкета" для знакомства с новым клиентом

        └── /rules/

            └── business_rules.json # 📖 "Свод законов" для принятия бизнес-решений

3. ⚙️ Подробное описание модулей и функций
Ядро логики (/app/core) - "Мозг"
Этот отдел нашего бота не претерпел изменений. Он по-прежнему является самым умным и отвечает за всю интеллектуальную работу.

llm_service.py (Связь с GigaChat)

Зачем нужен: Это наш шлюз для общения с большой языковой моделью. Он отвечает за то, чтобы запросы были правильными, а ответы — осмысленными.

correct_user_query(question): "Редактор". Прежде чем думать над ответом, эта функция отправляет вопрос пользователя в GigaChat с просьбой исправить опечатки. "Првет" превращается в "Привет".

is_query_relevant_ai(question, history): "Привратник". Определяет, относится ли вопрос к теме. Если пользователь спрашивает про погоду, эта функция ответит "Нет", и бот не будет тратить ресурсы на бесполезный ответ.

get_llm_response(question, history, context_key): "Главный аналитик". Самая важная функция. Она берет вопрос, историю диалога, добавляет к ним актуальную информацию из нашей базы знаний (project_info.pdf) и специальное указание (например, "говорить только о курсе для подростков"), а затем просит GigaChat сгенерировать развернутый, человечный ответ, который может содержать специальные команды (например, [START_BOOKING]).

template_service.py (Книга быстрых ответов)

Зачем нужен: Чтобы не беспокоить большой и дорогой AI по пустякам. На простые фразы вроде "Спасибо" или "Добрый день" бот должен отвечать мгновенно.

find_template(user_text, context_key): "Библиотекарь". Ищет в "картотеке" (templates.py) подходящий ответ. Сначала он смотрит в "ящике" для текущего контекста, а если не находит — в "общем".

choose_variant(variants): "Оратор". Если для одной фразы есть несколько вариантов ответа, эта функция выбирает один из них случайным образом, чтобы речь бота была более разнообразной.

business_logic.py (Движок правил)

Зачем нужен: Это самый хитрый модуль. Он позволяет задавать бизнес-логику, не программируя ее.

process_final_data(data): "Судья". Получает все данные, собранные от клиента (например, {'child_age': '9'}), открывает "Свод законов" (business_rules.json) и последовательно проверяет все правила. Если находит подходящее (например, "возраст между 9 и 13"), он добавляет к данным результат ('course_name': 'Основы...').

admin_notifications.py (Тревожная кнопка)

Зачем нужен: Чтобы бот не оставался один на один с проблемой.

notify_admin_on_error(...): Вызывается, если в сценарии произошел сбой. Отправляет администратору в Telegram подробное сообщение об ошибке с историей диалога.

notify_admin_on_suspicious_activity(...): Вызывается, если пользователь трижды задал нерелевантный вопрос. Уведомляет администратора о возможной спам-атаке.

Обработка сообщений (/app/handlers) - "Уши и Рот"
Этот отдел отвечает за все взаимодействие с пользователем и был значительно перестроен для поддержки сложных интерактивных сценариев.

sales_funnel.py (Главный Менеджер зала)

Зачем нужен: Это по-прежнему главный обработчик всех текстовых сообщений, но его роль кардинально изменилась. Он стал настоящим диспетчером команд.

handle_any_text(...): Этот менеджер больше не пытается сам вести диалог. Его задача — получить ответ от llm_service и проверить, есть ли в нем специальная команда-тег.

Если LLM вернул [START_BOOKING], менеджер не отправляет этот текст пользователю, а вызывает функцию start_booking_scenario из booking_handlers.py.

Если LLM вернул [CANCEL_BOOKING], он вызывает start_cancellation_flow из cancellation_handlers.py.

Если LLM вернул [START_ONBOARDING], он запускает сценарий знакомства из onboarding_handlers.py.

И только если никаких команд нет, он отправляет текст от LLM пользователю как обычный ответ.

booking_handlers.py (Администратор записи)

Зачем нужен: Этот новый, мощный модуль содержит всю логику многошагового процесса бронирования урока (FSM).

start_booking_scenario(...): "Входная точка". Запускается из sales_funnel, когда LLM дает команду начать бронирование.

_show_available_dates(...): "Смотритель расписания". Обращается к сервису bitrix_service за списком свободных слотов и рисует пользователю клавиатуру с доступными датами.

handle_date_selection(...) и handle_time_selection(...): "Консультанты". Последовательно обрабатывают нажатия пользователя на кнопки с датой и временем. В финале, когда все выбрано, вызывают book_lesson из bitrix_service, чтобы создать запись в Bitrix24, и сообщают пользователю об успехе.

cancellation_handlers.py (Отдел отмены)

Зачем нужен: Отвечает исключительно за процесс отмены записи.

start_cancellation_flow(...): "Сотрудник ресепшена". Запускается из sales_funnel, находит в локальной БД активный урок пользователя и вежливо запрашивает подтверждение отмены с помощью кнопок "Да" / "Нет".

confirm_cancellation(...): "Исполнитель". Срабатывает при нажатии на "Да, отменить". Вызывает cancel_booking из bitrix_cancel_service для удаления записи из CRM, а затем обновляет статус урока в локальной БД.

onboarding_handlers.py (Анкетолог)

Зачем нужен: Содержит FSM-сценарий знакомства с новым пользователем. Его логика не изменилась, но теперь он запускается по команде от sales_funnel.

Мост к Bitrix24 (/app/b24)
Это совершенно новый отдел, который служит надежным мостом между нашим ботом и внешней CRM-системой.

bitrix_service.py (Сервис бронирования)

Зачем нужен: Инкапсулирует всю логику по созданию сущностей в Bitrix24.

get_free_slots(...): "Планировщик". Отправляет запросы к REST API Bitrix24, чтобы получить события из календарей нужных преподавателей, анализирует их и возвращает чистый список свободных временных окон.

book_lesson(...): "Регистратор". Принимает данные о клиенте и выбранном времени, создает в Bitrix24 новое событие в календаре и связанную с ним задачу, а затем возвращает их ID для сохранения в нашей базе данных.

bitrix_cancel_service.py (Сервис отмены)

Зачем нужен: Предоставляет одну, но очень важную функцию для безопасного удаления записи.

cancel_booking(...): "Архивариус". Принимает task_id и event_id и последовательно отправляет два запроса в Bitrix24: один на удаление задачи, другой — на удаление события из календаря.

Память (/app/db)
Этот отдел отвечает за надежное хранение всей информации, и его роль стала еще важнее.

models.py (Чертежи)

Зачем нужен: Описывает для SQLAlchemy, как выглядят наши таблицы в базе данных.

User: Таблица для хранения информации о пользователях. Ее структура не изменилась: onboarding_completed и user_data для хранения ответов.

TrialLesson: Новая или обновленная таблица для хранения информации о пробных уроках. Ключевое нововведение: теперь здесь хранятся поля task_id и event_id — это "мостик", который связывает запись в нашей БД с конкретными сущностями в Bitrix24.

database.py (Строитель)

Зачем нужен: Содержит простые функции для выполнения сложных операций с базой данных. Его функции (get_or_create_user, save_history и т.д.) не изменились, но теперь появились новые, такие как add_trial_lesson (добавить урок) и cancel_lesson_db (изменить статус урока на отмененный).

Настраиваемая «Душа» (/app/knowledge_base)
Этот раздел остается сердцем проекта и вашей главной панелью управления. Все файлы здесь сохраняют свое предназначение.

lor.txt: Паспорт, характер и, что теперь особенно важно, должностная инструкция вашего AI, где вы указываете, в каких случаях он должен использовать командные теги ([START_BOOKING] и т.д.).

templates.py: Блокнот с быстрыми ответами.

fsm_scenario.json: Анкета для знакомства с клиентом.

business_rules.json: Свод законов для принятия решений.

project_info.pdf: Энциклопедия знаний вашего бота.

4. 🛠️ Расширение Функционала: Пошаговые Инструкции
Основа философии этого проекта — гибкость. Вы можете значительно изменить поведение бота, не написав ни строчки кода. Ниже приведены инструкции для самых частых сценариев доработки.

Часть 1: Базовое расширение (не требует навыков программирования)
Эти изменения выполняются путем редактирования простых текстовых и JSON-файлов в папке /app/knowledge_base. Они по-прежнему актуальны.

А. Как добавить новый вопрос в анкету знакомства
Предположим, вы хотите после увлечений ребенка дополнительно спросить, из какого он города.

Откройте файл сценария: app/knowledge_base/scenarios/fsm_scenario.json.

Найдите последний шаг: Сейчас это "awaiting_child_hobbies". У него поле "next_state" равно null, что означает конец сценария.

Создайте "мостик" к новому шагу: Измените "next_state": null у шага "awaiting_child_hobbies" на "next_state": "awaiting_city".

Опишите новый шаг: В конец списка states добавьте описание для нашего нового шага:

json
// ... предыдущие шаги
"awaiting_child_hobbies": {
  "question": "Спасибо! И последний вопрос: из какого вы города?", // Текст вопроса изменен
  "data_key": "child_hobbies",
  "next_state": "awaiting_city" // <-- Указываем на новый шаг
},
// Вот наш новый шаг
"awaiting_city": {
  "question": null, // <-- После этого вопроса бот ничего не спросит
  "data_key": "city", // <-- Ответ сохранится в 'личном деле' под ключом 'city'
  "next_state": null // <-- Это теперь конец сценария
}
// ...
Теперь бот будет задавать дополнительный вопрос про город, а ответ будет автоматически сохранен в базе данных.

Б. Как добавить новое бизнес-правило
Предположим, для детей 18 лет вы хотите предложить специальный "Профориентационный курс".

Откройте "Книгу правил": app/knowledge_base/rules/business_rules.json.

Добавьте новое правило: В массив "rules" добавьте новый объект по аналогии с существующими. Лучше всего разместить его перед правилом "для тех, кто слишком взрослый".

json
// ... правило для старшей группы (14-17 лет)
{
  "comment": "Правило для 18-летних.",
  "condition": {
    "key": "child_age",
    "type": "range", // Используем "range", чтобы поймать точное значение
    "value": [18, 18]
  },
  "action": {
    "type": "set_outcome",
    "key": "course_name",
    "value": "Профориентационный курс по IT-специальностям"
  }
},
{
  "comment": "Правило для тех, кто слишком взрослый (старше 17).",
  "condition": {
    "key": "child_age",
    "type": "greater_than",
    "value": 18 // <-- Важно! Измените значение с 17 на 18
  },
  // ...
}
Готово! Теперь "Движок правил" будет корректно обрабатывать и этот возраст.

В. Как добавить новый быстрый ответ
Предположим, вы хотите научить бота отвечать на вопрос: "А вы даете сертификат?".

Откройте "шпаргалку": app/knowledge_base/documents/templates.py.

Определите контекст: Этот вопрос не зависит от возраста, значит, его нужно добавить в общие шаблоны — "common".

Добавьте новый ключ и ответ:

python
TEMPLATES = {
    // ... другие контексты
    "common": {
        "спасибо/благодарю": [
            "Пожалуйста! Рад был помочь.",
        ],
        // Наш новый ответ
        "сертификат/документ об окончании/выдаете диплом": [
            "Да, конечно! После успешного завершения любого из наших курсов каждый ученик получает официальный сертификат от школы No Bugs, который станет отличным дополнением к его портфолио."
        ],
        "пока/до свидания": [
            "Всего доброго! Хорошего дня!",
        ]
    }
}
Теперь бот будет мгновенно и без помощи AI отвечать на этот вопрос.

Часть 2: Продвинутое расширение (требует изменения кода)
Эти изменения более сложные, но они раскрывают всю мощь новой архитектуры.

А. Как добавить новый тип условия в "Движок правил"
Задача: Научить движок проверять точное совпадение строки. Например, если пользователь из "Москвы", предложить ему очные занятия.

Откройте "мозг": app/core/business_logic.py.

Найдите функцию _check_condition: Она отвечает за проверку условий.

Добавьте новую логику: Внесите в функцию новый elif для обработки "type": "equals".

python
def _check_condition(condition: Dict, data: Dict) -> bool:
    # ... существующий код ...
    
    # Наша новая логика для сравнения строк
    elif condition_type == "equals":
        return user_value_str.lower() == str(condition_value).lower()
        
    return False
Используйте новое правило: Теперь в business_rules.json вы можете создавать правила нового типа.

Б. Как научить LLM запускать новый сложный сценарий (вместо "добавить кнопку")
Это ключевое отличие новой архитектуры. Раньше мы бы просто добавили кнопку и обработчик для нее. Теперь мы можем сделать гораздо больше: мы научим AI сам понимать, когда нужно запустить сложный процесс.

Задача: Научить бота по фразе "пришлите прайс-лист" или "какие у вас цены" запускать специальный сценарий, который формирует и отправляет сообщение с ценами.

Шаг 1: Придумайте команду для AI
Определите для LLM уникальный тег-команду, которую он будет возвращать вместо обычного текста. Например: [SEND_PRICE_LIST].

Шаг 2: Создайте "исполнителя" (новый обработчик)
В папке app/handlers создайте новый файл price_list_handler.py. Он будет содержать функцию, которая выполняет команду.

python
# app/handlers/price_list_handler.py
from aiogram import types
from aiogram.fsm.context import FSMContext

async def send_price_list_scenario(message: types.Message, state: FSMContext):
    """
    Формирует и отправляет пользователю сообщение с прайс-листом.
    """
    await state.clear() # На всякий случай сбрасываем состояния
    price_text = (
        "Конечно, вот наш актуальный прайс-лист:\n\n"
        "Курс 'Основы Python' - 10 000 руб.\n"
        "Курс 'Веб-разработка' - 15 000 руб.\n"
        "Пробный урок - бесплатно!"
    )
    await message.answer(price_text)
Шаг 3: Научите "Менеджера зала" новой команде
Откройте app/handlers/sales_funnel.py. Нам нужно научить его распознавать новый тег и вызывать нашего "исполнителя".

python
# app/handlers/sales_funnel.py
# ... вверху, где импорты
from app.handlers import price_list_handler # <-- импортируем наш новый модуль

# ... внутри функции handle_any_text, где идет проверка ответа от LLM
async def handle_any_text(message: types.Message, state: FSMContext):
    # ...
    llm_response = await get_llm_response(...)
    
    if "[START_BOOKING]" in llm_response:
        # ...
    # Вот наше новое правило
    elif "[SEND_PRICE_LIST]" in llm_response:
        logging.info(f"LLM вернул команду на отправку прайса для {user.id}.")
        await price_list_handler.send_price_list_scenario(message, state)
    
    else:
        await message.answer(llm_response)
    # ...
Шаг 4: Обновите инструкцию для "Мозга" (LLM)
Откройте "паспорт" нашего AI: app/knowledge_base/documents/lor.txt. Добавьте в его должностную инструкцию новое, четкое правило:

"Важно! Если пользователь спрашивает о ценах, стоимости или просит прайс-лист, твой единственный ответ должен быть специальным тегом: [SEND_PRICE_LIST]. Не пиши ничего другого."

Результат: Теперь, когда пользователь напишет "сколько стоят ваши курсы?", произойдет следующее:

Запрос уйдет в GigaChat.

GigaChat, следуя инструкции, вернет не текст, а только команду [SEND_PRICE_LIST].

sales_funnel "увидит" эту команду и вместо отправки текста пользователю вызовет send_price_list_scenario.

Пользователь получит аккуратно отформатированный прайс-лист.

Таким образом, мы отделили принятие решения (задача LLM) от его исполнения (задача Python-кода), что делает систему невероятно гибкой.

5. 🤖 Инструкция для другого ИИ (System Prompt для Преемника)
System Prompt Overview for Language Model Successor:

My core architectural principle is the strict separation of the universal application Engine (located in /app) from the project-specific Knowledge Base (located in /app/knowledge_base). Your primary directive is to never modify the Python code within the /app directory. All adaptations, personalizations, and business logic changes are to be performed exclusively by editing the configuration files within /knowledge_base.

Key Architectural Concepts:

Proactive Onboarding: I do not wait for user commands. Upon detecting a new user (identified by the onboarding_completed flag in the users table being False), handle_any_text in /app/handlers/sales_funnel.py immediately initiates an FSM-driven onboarding script.

Declarative FSM: The entire onboarding flow (questions, validation, data keys) is defined in /app/knowledge_base/scenarios/fsm_scenario.json. The FSM engine in sales_funnel.py is a generic interpreter of this file. To change the onboarding process, you modify the JSON, not the Python code.

Rule-Based Logic Engine: All business logic (e.g., product recommendations based on user data) is externalized to /app/knowledge_base/rules/business_rules.json. The Python module /app/core/business_logic.py is a universal rule engine that processes this file. It is designed to be extensible (e.g., for new condition types like "equals" or "contains") but should not contain project-specific if/else statements.

Context-Aware Templating: Quick responses are managed by /app/core/template_service.py, which reads from /app/knowledge_base/documents/templates.py. This template file is structured with context keys (e.g., "course_junior", "course_senior", "default"). The main handler (sales_funnel.py) determines the appropriate context_key based on the user's stored data and passes it to both the template service and the LLM service.

Context-Aware RAG: The primary LLM handler, get_llm_response in /app/core/llm_service.py, accepts the context_key. This key is used to inject a high-priority directive into the system prompt, forcing the model to focus its response on the relevant context (e.g., a specific course).

Your Adaptation Workflow:

To adapt my function for a new business case (e.g., a car wash), you must perform the following steps only within /app/knowledge_base:

Modify Persona: Edit /documents/lor.txt to define the new AI persona.

Modify Onboarding Script: Rewrite /scenarios/fsm_scenario.json with questions relevant to the new business (e.g., car model, service type).

Modify Business Rules: Rewrite /rules/business_rules.json to define the new decision-making logic (e.g., if car_model is "SUV", recommend "premium_wash").

Modify Quick Replies: Update /documents/templates.py with new contextual templates.

Update Knowledge Source: Replace /documents/project_info.pdf with the new company's service manual or price list.

Do not alter the Python source code. The engine is designed to be universal. Your task is to provide it with a new "soul" and "brain" through the configuration files.
