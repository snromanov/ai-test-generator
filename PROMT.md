# AI Test Generator - Руководство для CLI агентов

Это руководство предназначено для CLI агентов (Claude Code, Qwen Code, Cursor и др.), которые помогают генерировать тест-кейсы на основе требований.

## Быстрый старт

```bash
# Проверить текущее состояние
python main.py state show

# Создать новую сессию (claude_code, qwen_code, cursor, aider)
python main.py state new --agent <agent_type>

# Посмотреть что делать дальше
python main.py state resume
```

## Структура проекта

Для получения актуальной структуры выполни:
```bash
python main.py info
```

Основные модули:
- `src/agents/` - модели данных и хелперы для тест-кейсов
- `src/generators/` - загрузка требований и экспорт в Excel/CSV
- `src/parsers/` - парсер Confluence
- `src/prompts/` - промпты для генерации тестов
- `src/state/` - State Manager для сохранения контекста
- `src/utils/` - логирование и информация о проекте

## КРИТИЧЕСКИ ВАЖНО: State Management

### Почему это важно

State Manager предотвращает:
- **Потерю контекста** между сессиями
- **Галлюцинации** - есть "источник истины"
- **Дублирование работы** - видно что уже сделано
- **Несогласованность** - единое состояние для всех операций

### Обязательные действия агента

#### 1. В начале работы - ВСЕГДА проверяй состояние

```bash
python main.py state show
```

Если сессия существует - продолжай с места остановки.
Если нет - создай новую:

```bash
python main.py state new --agent <agent_type>  # claude_code, qwen_code, cursor, aider
```

#### 2. При добавлении требований - сохраняй в state

```bash
python main.py state add "Текст требования"
```

Или программно через Python:
```python
from src.state import StateManager

sm = StateManager()
sm.get_or_create_session(agent_type="<agent_type>")
sm.add_requirement("Текст требования", source="file", source_ref="requirements.md")
sm.save()
```

#### 3. При генерации тестов - обновляй прогресс

```python
sm.update_progress(step="analyzing", current_requirement_id="REQ-001")
sm.set_requirement_analysis(
    req_id="REQ-001",
    inputs=["email", "password"],
    outputs=["auth_token", "user_profile"],
    business_rules=["Email должен быть валидным"],
    states=[]
)
sm.update_requirement_status("REQ-001", RequirementStatus.ANALYZED)
```

#### 4. После добавления тестов - фиксируй результат

```python
from src.state import TestCaseState

tc = TestCaseState(
    id="TC-001",
    title="Успешный вход с валидными данными",
    priority="High",
    test_type="Positive",
    technique="Use Case Testing",
    preconditions=["Пользователь зарегистрирован"],
    steps=[{"step": 1, "action": "Открыть страницу входа"}],
    expected_result="Пользователь авторизован"
)
sm.add_test_case("REQ-001", tc)
```

#### 5. Добавляй заметки для отслеживания

```bash
python main.py state note "Пользователь попросил добавить негативные тесты"
```

### Восстановление контекста

Если потерял контекст - выполни:

```bash
python main.py state context
```

Это выведет полное состояние в читаемом формате.

## Рабочий процесс генерации тестов

### Шаг 1: Получение требований

```bash
# Из файла
python main.py load-file requirements.md

# Из Confluence
python main.py load-confluence PAGE_ID

# Использование демо-требований (Petstore)
python main.py load-demo --name petstore
```

### Шаг 2: Анализ требования

Перед генерацией тестов проанализируй требование:

```
## Анализ REQ-001

**Входные данные:**
- email (строка, формат email)
- password (строка, 8-20 символов)

**Выходные данные:**
- auth_token (JWT)
- error_message (если ошибка)

**Бизнес-правила:**
- Email должен быть уникальным
- Пароль минимум 8 символов
- Максимум 3 попытки входа

**Состояния:** N/A
```

Сохрани анализ:
```python
sm.set_requirement_analysis("REQ-001", inputs, outputs, rules, states)
```

### Шаг 3: Выбор техник тест-дизайна

| Техника | Применять когда |
|---------|-----------------|
| Equivalence Partitioning | Есть классы входных данных |
| Boundary Value Analysis | Есть диапазоны значений |
| Decision Table | Комбинации условий |
| State Transition | Объекты со статусами |
| Use Case Testing | Сценарии пользователя |
| Pairwise | Много параметров |
| Error Guessing | Всегда дополнительно |

### Шаг 4: Генерация тест-кейсов

Формат тест-кейса (ДЕТАЛИЗИРОВАННЫЙ):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TC-PET-001: Успешное создание питомца со всеми полями
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Приоритет: High
Тип: Positive
Техника: Use Case Testing - Happy Path

Предусловия:
  • API сервер доступен
  • Эндпоинт POST /pet активен

Шаги:
  1. Отправить POST /pet с body:
     {
       "id": 100,
       "name": "Doggie",
       "photoUrls": ["https://example.com/photo1.jpg"],
       "status": "available",
       "category": {"id": 1, "name": "Dogs"},
       "tags": [{"id": 1, "name": "friendly"}]
     }
  2. Проверить код ответа
  3. Проверить все поля в ответе
  4. Выполнить GET /pet/100 для верификации

Ожидаемый результат:
  1. Код ответа: 201 Created
  2. Response body содержит:
     - id: 100
     - name: "Doggie"
     - photoUrls: ["https://example.com/photo1.jpg"]
     - status: "available"
  3. GET /pet/100 возвращает созданного питомца
  4. Все поля совпадают с отправленными
```

**Ключевые правила детализации:**
- В шагах ВСЕГДА указывать конкретный JSON body
- В ожидаемых результатах ВСЕГДА указывать код + проверяемые поля
- Добавлять верификацию через связанные эндпоинты (GET после POST)
- Указывать негативные проверки (что НЕ должно произойти)

### Шаг 5: Ревью и доработка

После генерации тестов:
1. Представь их пользователю
2. Получи фидбек
3. Обнови статусы:

```python
sm.update_test_case_status("REQ-001", "TC-001", "approved")
sm.update_test_case_status("REQ-001", "TC-002", "rejected", "Дублирует TC-001")
```

### Шаг 6: Экспорт

```bash
python main.py state export -f excel -o artifacts/test_cases
```

## CLI команды

### Основные команды

```bash
# Генерация из файла
python main.py file <path> -o <output> -f excel

# Генерация из Confluence
python main.py confluence <page_id> -o <output>

# Интерактивный режим
python main.py interactive

# Показать техники тест-дизайна
python main.py techniques

# Показать промпт для агента
python main.py agent-prompt
```

### Команды State Manager

```bash
# Показать состояние
python main.py state show
python main.py state show -f json

# Создать сессию
python main.py state new -a <agent_type>

# Добавить требование
python main.py state add "Текст требования"

# Получить контекст для восстановления
python main.py state context

# Что делать дальше
python main.py state resume

# Добавить заметку
python main.py state note "Важная заметка"

# Экспорт результатов
python main.py state export -o artifacts/test_cases -f excel

# Очистить состояние
python main.py state clear
```

## Техники тест-дизайна

### 1. Equivalence Partitioning

```
Требование: Возраст 18-65 лет

Классы:
- Невалидный: < 0 (отрицательный)
- Невалидный: 0-17 (несовершеннолетний)
- Валидный: 18-65 (допустимый)
- Невалидный: > 65 (превышение)

Тесты: по одному из каждого класса
```

### 2. Boundary Value Analysis

```
Требование: Пароль 8-20 символов

Граничные значения:
- 7 символов (min-1) → ошибка
- 8 символов (min) → OK
- 9 символов (min+1) → OK
- 19 символов (max-1) → OK
- 20 символов (max) → OK
- 21 символ (max+1) → ошибка
```

### 3. Decision Table

```
Условия: Premium + Сумма > 1000 + Купон

| Premium | >1000 | Купон | Скидка |
|---------|-------|-------|--------|
| Да      | Да    | Да    | 30%    |
| Да      | Да    | Нет   | 20%    |
| Да      | Нет   | Да    | 15%    |
| Нет     | Да    | Да    | 10%    |
| Нет     | Нет   | Нет   | 0%     |
```

### 4. State Transition

```
Заказ: Новый → Оплачен → В сборке → Отправлен → Доставлен

Валидные переходы:
- Новый → Оплачен ✓
- Оплачен → В сборке ✓
- В сборке → Отправлен ✓

Невалидные переходы:
- Новый → Отправлен ✗
- Доставлен → Оплачен ✗
```

### 5. Error Guessing

Всегда проверяй:
- Пустые значения, null, undefined
- Спецсимволы: `<script>`, `' OR 1=1`
- Очень длинные строки (10000+ символов)
- Некорректные форматы (email без @)
- Граничные даты (29.02, 31.11)
- Unicode и эмодзи

## Файл состояния

State Manager сохраняет состояние в `.test_generator_state.json`:

```json
{
  "session_id": "20250114_153022",
  "agent_type": "<agent_type>",
  "progress": {
    "total_requirements": 5,
    "processed_requirements": 3,
    "current_step": "generating"
  },
  "requirements": [
    {
      "id": "REQ-001",
      "status": "completed",
      "test_cases": [...]
    }
  ]
}
```

**Не редактируй этот файл вручную!** Используй StateManager API.

## Конфигурация

`.env` файл:

```ini
# Confluence (опционально, для загрузки требований)
CONFLUENCE_URL=https://company.atlassian.net/wiki
CONFLUENCE_USER=email@company.com
CONFLUENCE_TOKEN=xxx

# Logging
LOG_LEVEL=INFO
```

## Советы для агентов

1. **Всегда начинай с `state show`** - понять текущий контекст
2. **Сохраняй после каждого действия** - `sm.save()`
3. **Используй `state note`** для важных решений
4. **Проверяй `state resume`** если не уверен, что делать
5. **Не галлюцинируй** - если требование неясно, спроси пользователя
6. **Приоритизируй** - Critical/High для важного, Medium/Low для остального
7. **Группируй тесты** - по функциональности или технике

## Жесткие правила генерации (добавь в системный промпт агента)

1. **Layer gating**: если требование помечено [Front]/[UI], генерируй ТОЛЬКО UI-тесты.  
   Запрещено выдумывать API, эндпоинты, JSON body, статусы ответа, если они не указаны.
2. **Никаких "N/A"**: в шагах и предусловиях не должно быть заглушек.
3. **Трассируемость по пунктам**: каждый пункт требования должен иметь минимум один тест-кейс.  
   Если для пункта невозможно написать тест — перечисли его в `coverage_gaps`.
4. **Assumptions/Questions**: если деталей не хватает, явно зафиксируй допущения и вопросы.
5. **Не придумывай данные**: если нет конкретных значений, укажи "данные подготовлены" в предусловиях.
