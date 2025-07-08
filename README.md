AI-Менеджер для Telegram: Полная Документация
1. Введение: Философия проекта

Добро пожаловать в документацию по универсальному AI-менеджеру для Telegram! Это не просто чат-бот, а полноценная платформа для создания проактивных, эмпатичных и продающих цифровых сотрудников.

Ключевая философия проекта — полное и бескомпромиссное разделение Кода (Движка) и Знаний (Конфигурации).

Представьте, что мы создали идеальный автомобильный двигатель (/app). Он мощный, надежный и универсальный. А вы, как владелец, можете поставить этот двигатель в любой кузов (/knowledge_base) — будь то спортивный автомобиль, семейный минивэн или внедорожник. Вы меняете внешний вид, салон и даже правила дорожного движения, по которым он едет, не залезая внутрь самого двигателя.

Это позволяет любому человеку, даже без навыков программирования, полностью изменить личность, сценарии и бизнес-логику бота, просто отредактировав несколько текстовых файлов.

2. 🏛️ Архитектура проекта: Как устроен наш «Автомобиль»
Проект состоит из четко разделенных модулей, каждый из которых выполняет свою уникальную роль.

text
/nobugs_bot
├── .env                  # Сейф с секретными ключами (пароль от Telegram и т.д.)
├── Dockerfile            # Инструкция для сборки "коробки" с нашим ботом (для Docker)
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
    ├── /handlers         # 🗣️ "Уши и Рот" - все, что связано с приемом и отправкой сообщений
    │   ├── common.py              # Обработка команды /start
    │   ├── sales_funnel.py        # 🤵 Главный "Менеджер зала" - обрабатывает все диалоги
    │   └── callback_handlers.py   # 👆 "Панель управления" - обрабатывает нажатия на кнопки
    |
    ├── /db               # 💾 "Память" - все, что связано с хранением информации
    │   ├── models.py              # 📝 "Чертежи" базы данных - как выглядят таблицы
    │   └── database.py            # 👷 "Строитель" - умеет записывать и читать из БД
    |
    ├── /keyboards        # ⌨️ "Приборная панель" - создает кнопки для пользователя
    │   ├── callbacks.py           # "Фабрика" уникальных меток для кнопок
    │   └── inline.py              # "Сборщик" - собирает клавиатуру из кнопок
    |
    └── /knowledge_base   # ❤️ "Душа и Характер" - настраиваемая часть бота (ваш "Кузов")
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
Это самый умный отдел нашего бота.

llm_service.py (Связь с GigaChat)

Зачем нужен: Это наш шлюз для общения с большой языковой моделью GigaChat. Он отвечает за то, чтобы запросы были правильными, а ответы — осмысленными.

correct_user_query(question): "Редактор". Прежде чем думать над ответом, эта функция отправляет вопрос пользователя в GigaChat с просьбой исправить опечатки. "Првет" превращается в "Привет".

is_query_relevant_ai(question, history): "Привратник". Определяет, относится ли вопрос к теме. Если пользователь спрашивает про погоду, эта функция ответит "Нет", и бот не будет тратить ресурсы на бесполезный ответ.

get_llm_response(question, history, context_key): "Главный аналитик". Самая важная функция. Она берет вопрос, историю диалога, добавляет к ним актуальную информацию из нашей базы знаний (project_info.pdf) и специальное указание (например, "говорить только о курсе для подростков"), а затем просит GigaChat сгенерировать развернутый, человечный ответ.

template_service.py (Книга быстрых ответов)

Зачем нужен: Чтобы не беспокоить большой и дорогой AI по пустякам. На простые фразы вроде "Спасибо" или "Добрый день" бот должен отвечать мгновенно.

find_template(user_text, context_key): "Библиотекарь". Ищет в "картотеке" (templates.py) подходящий ответ. Сначала он смотрит в "ящике" для текущего контекста (например, course_junior), а если не находит — в "общем" ящике.

choose_variant(variants): "Оратор". Если для одной фразы есть несколько вариантов ответа, эта функция выбирает один из них случайным образом, чтобы речь бота была более разнообразной.

business_logic.py (Движок правил)

Зачем нужен: Это самый хитрый модуль. Он позволяет задавать бизнес-логику, не программируя ее.

process_final_data(data): "Судья". Получает все данные, собранные от клиента (например, {'child_age': '9'}), открывает "Свод законов" (business_rules.json) и последовательно проверяет все правила. Если находит подходящее (например, "возраст между 9 и 13"), он добавляет к данным результат ('course_name': 'Основы...'). Эта функция также использует библиотеку pymorphy3 для правильного склонения имен.

admin_notifications.py (Тревожная кнопка)

Зачем нужен: Чтобы бот не оставался один на один с проблемой.

notify_admin_on_error(...): Вызывается, если в сценарии произошел сбой. Отправляет администратору в Telegram подробное сообщение об ошибке с историей диалога.

notify_admin_on_suspicious_activity(...): Вызывается, если пользователь трижды задал нерелевантный вопрос. Уведомляет администратора о возможной спам-атаке.

Обработка сообщений (/app/handlers) - "Уши и Рот"
Этот отдел отвечает за все взаимодействие с пользователем.

common.py (handle_start)

Зачем нужен: Для обработки самой первой команды /start.

handle_start(...): Больше не содержит никакой логики. Просто берет приветственный текст из templates.py и отправляет его пользователю, чтобы даже эта первая фраза была настраиваемой.

sales_funnel.py (handle_any_text)

Зачем нужен: Это главный "Менеджер зала", который обрабатывает все текстовые сообщения и решает, что с ними делать.

handle_any_text(...): Это очень умный менеджер.

Сначала он смотрит на клиента: "Я его знаю?". Он проверяет в базе данных флаг onboarding_completed.

Если клиент новый, он не ждет вопросов, а сам начинает диалог: "Здравствуйте! Давайте познакомимся!" и запускает сценарий сбора данных (start_fsm_scenario).

Если клиент в процессе знакомства, менеджер работает как "анкетолог": берет ответ, сохраняет его, задает следующий вопрос из fsm_scenario.json и терпеливо ждет.

Если клиент уже знакомый, менеджер работает как "эксперт": определяет контекст (например, "ага, это тот папа с 9-летним сыном"), передает вопрос и контекст в template_service и llm_service и дает точный, персонализированный ответ. Здесь же работает система безопасности, которая отсеивает нерелевантные вопросы.

callback_handlers.py (Обработка кнопок)

Зачем нужен: Чтобы наши кнопки не были просто красивым украшением.

handle_program_details(...): "Ловит" нажатие на кнопку "Узнать подробнее" и отправляет развернутое описание курса.

handle_book_trial(...): "Ловит" нажатие на кнопку "Подобрать время" и отправляет клиенту сообщение, что заявка принята, а администратору — уведомление.

Память (/app/db)
Этот отдел отвечает за надежное хранение всей информации.

models.py (Чертежи)

Зачем нужен: Описывает для SQLAlchemy, как должны выглядеть наши таблицы в базе данных.

User: Таблица для хранения информации о пользователях. Ключевые поля: onboarding_completed (флаг, прошел ли знакомство) и user_data (JSON-поле, где хранятся все ответы из анкеты, как в "личном деле").

DialogHistory: Таблица, где хранится каждое сообщение в диалоге с привязкой к пользователю.

database.py (Строитель)

Зачем нужен: Содержит простые функции для выполнения сложных операций с базой данных.

get_or_create_user(...): Найти пользователя в БД, а если его нет — создать.

save_history(...): Сохранить одно сообщение в историю.

set_onboarding_completed(...): Поставить "галочку" в "личном деле" пользователя, что он прошел знакомство.

Настраиваемая «Душа» (/app/knowledge_base)
Это ваша личная "панель управления" ботом. Именно здесь и только здесь вы будете работать, чтобы адаптировать его под свои нужды.

lor.txt: Паспорт, характер и должностная инструкция вашего AI. Простой текстовый файл.

templates.py: Блокнот с быстрыми ответами. Простой Python-словарь.

fsm_scenario.json: Анкета для знакомства с клиентом. Простой JSON-файл.

business_rules.json: Свод законов для принятия решений. Простой JSON-файл.

project_info.pdf: Энциклопедия знаний вашего бота. Любой PDF-документ.

5. 🛠️ Расширение Функционала: Пошаговые Инструкции
Основа философии этого проекта — гибкость. Вы можете значительно изменить поведение бота, не написав ни строчки кода. Ниже приведены инструкции для самых частых сценариев доработки.

Часть 1: Базовое расширение (не требует навыков программирования)
Эти изменения выполняются путем редактирования простых текстовых и JSON-файлов в папке /app/knowledge_base.

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
Эти изменения более сложные и требуют базового понимания Python.

А. Как добавить новый тип условия в "Движок правил"
Задача: Научить движок проверять точное совпадение строки. Например, если пользователь из "Москвы", предложить ему очные занятия.

Откройте "мозг": app/core/business_logic.py.

Найдите функцию _check_condition: Она отвечает за проверку условий.

Добавьте новую логику: Внесите в функцию новый elif для обработки "type": "equals".

python
def _check_condition(condition: Dict, data: Dict) -> bool:
    """Универсальная функция для проверки одного условия."""
    key_to_check = condition.get("key")
    condition_type = condition.get("type")
    condition_value = condition.get("value")
    
    user_value_str = str(data.get(key_to_check, ''))

    # Проверка на числовые значения (остается без изменений)
    if condition_type in ["range", "less_than", "greater_than"]:
        if not user_value_str.isdigit():
            return False
        user_value_int = int(user_value_str)
        # ... логика для range, less_than, greater_than
    
    # Наша новая логика для сравнения строк
    elif condition_type == "equals":
        return user_value_str.lower() == str(condition_value).lower()
        
    return False
Используйте новое правило: Теперь в business_rules.json вы можете создавать правила нового типа:

json
{
  "comment": "Специальное предложение для жителей Москвы.",
  "condition": {
    "key": "city", // <-- ключ из анкеты, который мы добавили ранее
    "type": "equals",
    "value": "Москва"
  },
  "action": { ... }
}
Б. Как добавить новую кнопку в финальное меню
Задача: Добавить кнопку "Посмотреть отзывы".

Откройте "Сборщик" клавиатуры: app/keyboards/inline.py.

Добавьте новую кнопку: Внутри функции get_enroll_keyboard добавьте в список buttons новый элемент.

python
def get_enroll_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="Узнать подробнее о программе",
                callback_data=EnrollmentCallback(action="program_details").pack()
            )
        ],
        # Наша новая кнопка
        [
            InlineKeyboardButton(
                text="Посмотреть отзывы",
                callback_data=EnrollmentCallback(action="show_reviews").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="Подобрать время для пробного урока",
                callback_data=EnrollmentCallback(action="book_trial").pack()
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
Откройте "Панель управления" кнопками: app/handlers/callback_handlers.py.

Создайте новый обработчик: Добавьте новую функцию, которая будет "ловить" нажатие на кнопку с action="show_reviews".

python
# ... импорты и существующие обработчики

@router.callback_query(EnrollmentCallback.filter(F.action == "show_reviews"))
async def handle_show_reviews(query: types.CallbackQuery):
    """
    Обрабатывает нажатие на кнопку "Посмотреть отзывы".
    """
    text = (
        "Вот что говорят родители о наших курсах:\n\n"
        "Елена, мама 12-летнего Ивана:\n'Никогда не думала, что сын так увлечется! "
        "Теперь вместо игр он пишет для них код. Спасибо No Bugs!'\n\n"
        "Михаил, отец 15-летней Анны:\n'Отличная подача материала. "
        "Дочь не просто учит синтаксис, а решает реальные задачи'."
    )
    await query.message.answer(text)
    await query.answer()
Перезапустите бота. Новая кнопка появится и будет корректно работать.

4. 🤖 Инструкция для другого ИИ (System Prompt для Преемника)
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
