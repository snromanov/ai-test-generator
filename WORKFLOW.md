# Workflow для CLI агентов

Этот документ описывает полный процесс работы с AI Test Generator для CLI агентов (Claude Code, Qwen Code, Cursor и др.).

## Быстрый старт

### 1. Загрузка требований

```bash
# Загрузить демо-требования
./venv/bin/python main.py load-demo -n petstore

# Загрузить из файла
./venv/bin/python main.py load-file requirements.md

# Загрузить из Confluence (требует настройки .env)
./venv/bin/python main.py load-confluence PAGE_ID
```

### 2. Проверить состояние

```bash
./venv/bin/python main.py state show
```

Вы увидите:
- Список загруженных требований
- Статус каждого требования (pending/completed)
- Количество тест-кейсов для каждого требования

### 3. Генерация тест-кейсов

Создайте Python скрипт или используйте интерактивную сессию:

```python
from src.utils.test_generator_helper import TestGeneratorHelper

# Инициализация
helper = TestGeneratorHelper()

# Получить необработанные требования
pending = helper.get_pending_requirements()
print(f"Необработано: {len(pending)} требований")

# Выбрать требование
req_id = pending[0]['id']  # Например, REQ-003
req_text = helper.get_requirement_text(req_id)

# Анализ требования
helper.add_analysis(
    req_id=req_id,
    inputs=['id', 'name', 'status'],
    outputs=['201 Created', '400 Bad Request'],
    business_rules=[
        'id должен быть > 0',
        'name: 2-50 символов'
    ],
    states=['available', 'pending'],
    suggested_techniques=['boundary_value', 'equivalence_partitioning']
)

# Создать тест-кейсы
test_cases = [
    {
        'id': 'TC-003-001',
        'title': 'Успешное создание с валидными данными',
        'priority': 'High',
        'test_type': 'Positive',
        'technique': 'equivalence_partitioning',
        'preconditions': ['API доступен'],
        'steps': [{'step': 1, 'action': 'Отправить POST запрос'}],
        'expected_result': 'Код ответа: 201 Created'
    }
]

# Добавить тесты
helper.add_test_cases_bulk(req_id, test_cases)

# Отметить как завершенное
helper.mark_requirement_completed(req_id)

# Статистика
stats = helper.get_statistics()
print(f"Прогресс: {stats['completed_requirements']}/{stats['total_requirements']}")
```

### 3.1 Быстрый автопоток (analyzer + generators)

Автоматически анализирует требования, добавляет анализ и базовый набор тестов
(CRUD + EP/BVA где возможно).

```bash
./venv/bin/python - <<'PY'
from src.utils.test_generator_helper import (
    TestGeneratorHelper,
    create_api_crud_test_suite,
    create_boundary_test_cases,
    create_equivalence_test_cases,
)
from src.utils.requirement_analyzer import RequirementAnalyzer

helper = TestGeneratorHelper()
analyzer = RequirementAnalyzer()

pending = helper.get_pending_requirements()
print(f"Pending: {len(pending)}")

for req_info in pending:
    req_id = req_info["id"]
    req_text = helper.get_requirement_text(req_id)

    analysis = analyzer.analyze(req_text, req_id)
    helper_params = analyzer.to_helper_format(analysis)
    helper.add_analysis(req_id=req_id, **helper_params)

    base_tc_id = f"TC-{req_id.split('-')[1]}"
    crud_tests = create_api_crud_test_suite(
        req_id=req_id,
        base_tc_id=base_tc_id,
        endpoint=analysis.endpoint,
        http_method=analysis.http_method,
        req_type=analysis.requirement_type,
        preconditions=["API доступен"],
    )
    helper.add_test_cases_bulk(req_id, crud_tests)

    for field, bounds in analysis.boundary_values.items():
        if not all(k in bounds for k in ("min", "max")):
            continue
        try:
            valid_example = (bounds["min"] + bounds["max"]) // 2
            invalid_low = bounds["min"] - 1
            invalid_high = bounds["max"] + 1
        except TypeError:
            continue

        bva_tests = create_boundary_test_cases(
            req_id=req_id,
            base_tc_id=f"{base_tc_id}-{field.upper()}",
            field_name=field,
            min_value=bounds["min"],
            max_value=bounds["max"],
            valid_example=valid_example,
            invalid_low=invalid_low,
            invalid_high=invalid_high,
            endpoint=analysis.endpoint,
        )
        helper.add_test_cases_bulk(req_id, bva_tests)

    for field, classes in analysis.equivalence_classes.items():
        if not classes.get("valid") and not classes.get("invalid"):
            continue
        ep_tests = create_equivalence_test_cases(
            req_id=req_id,
            base_tc_id=f"{base_tc_id}-{field.upper()}",
            field_name=field,
            valid_values=classes.get("valid", []),
            invalid_values=classes.get("invalid", []),
            endpoint=analysis.endpoint,
        )
        helper.add_test_cases_bulk(req_id, ep_tests)

    helper.mark_requirement_completed(req_id)
    print(f"Completed {req_id}")

stats = helper.get_statistics()
print(stats)
PY
```

### 4. Использование генераторов шаблонов

Для типовых тестов используйте встроенные генераторы:

```python
from src.utils.test_generator_helper import (
    create_boundary_test_cases,
    create_equivalence_test_cases
)

# Граничные значения
bva_tests = create_boundary_test_cases(
    req_id='REQ-003',
    base_tc_id='TC-003',
    field_name='quantity',
    min_value=1,
    max_value=100,
    valid_example=50,
    invalid_low=0,
    invalid_high=101,
    preconditions=['API доступен'],
    endpoint='POST /store/order'
)

# Классы эквивалентности
ep_tests = create_equivalence_test_cases(
    req_id='REQ-003',
    base_tc_id='TC-003',
    field_name='status',
    valid_values=['available', 'pending', 'sold'],
    invalid_values=['unknown', 'deleted'],
    preconditions=['API доступен'],
    endpoint='POST /pet'
)

# Добавить сгенерированные тесты
helper = TestGeneratorHelper()
helper.add_test_cases_bulk('REQ-003', bva_tests + ep_tests)
```

### 5. Экспорт результатов

```bash
# Создать директорию для артефактов (если не существует)
mkdir -p artifacts

# Экспорт в Excel и CSV
./venv/bin/python main.py state export -o artifacts/test_cases -f both

# Только Excel
./venv/bin/python main.py state export -o artifacts/test_cases -f excel

# Только CSV
./venv/bin/python main.py state export -o artifacts/test_cases -f csv
```

## Техники тест-дизайна

### Boundary Value Analysis (BVA)

Используйте для полей с ограничениями:

```python
# Пример: поле quantity от 1 до 100
test_cases = [
    # Граница минимума
    {'id': 'TC-001', 'value': 1, 'expected': '200 OK'},
    {'id': 'TC-002', 'value': 0, 'expected': '400 Bad Request'},
    
    # Граница максимума
    {'id': 'TC-003', 'value': 100, 'expected': '200 OK'},
    {'id': 'TC-004', 'value': 101, 'expected': '400 Bad Request'},
]
```

### Equivalence Partitioning (EP)

Разделите входные данные на классы:

```python
# Пример: статус питомца
valid_classes = ['available', 'pending', 'sold']
invalid_classes = ['unknown', 'deleted', '', None]

# По одному тесту на класс
for status in valid_classes:
    # Создать позитивный тест
    pass
    
for status in invalid_classes:
    # Создать негативный тест
    pass
```

### State Transition

Для объектов с жизненным циклом:

```python
# Пример: статусы заказа
transitions = [
    ('placed', 'approved'),      # Валидный переход
    ('approved', 'delivered'),   # Валидный переход
    ('delivered', 'placed'),     # Невалидный переход
    ('sold', 'available'),       # Невалидный переход
]

for from_state, to_state in transitions:
    # Создать тест проверки перехода
    pass
```

## Полезные команды

### Подготовка к новой генерации

Перед началом работы над новым набором требований:

```bash
# Подготовить проект (с бэкапом artifacts)
./venv/bin/python -m src.utils.cleanup --prepare

# Подготовить без бэкапа
./venv/bin/python -m src.utils.cleanup --prepare --no-backup

# Предпросмотр (без удаления)
./venv/bin/python -m src.utils.cleanup --prepare --dry-run
```

Команда `--prepare` выполняет:
1. Создает бэкап директории `artifacts/` с timestamp (например, `artifacts_backup_20260114_172027/`)
2. Удаляет state файлы (.test_generator_state.json)
3. Очищает директорию artifacts/
4. Удаляет кэш (__pycache__, .pytest_cache и т.д.)
5. Удаляет временные файлы (.pyc, .DS_Store и т.д.)

### Управление состоянием

```bash
# Показать текущее состояние
./venv/bin/python main.py state show

# Создать новую сессию
./venv/bin/python main.py state new --agent claude_code

# Показать полный контекст
./venv/bin/python main.py state context

# Показать что делать дальше
./venv/bin/python main.py state resume

# Очистить состояние (осторожно!)
./venv/bin/python main.py state clear
```

### Информационные команды

```bash
# Доступные техники тест-дизайна
./venv/bin/python main.py techniques

# Информация о проекте
./venv/bin/python main.py info

# Промпт для CLI агента
./venv/bin/python main.py agent-prompt
```

## Примеры для разных типов требований

### REST API эндпоинт (POST)

```python
helper.add_analysis(
    req_id='REQ-003',
    inputs=['id', 'name', 'photoUrls', 'status'],
    outputs=['201 Created', '400 Bad Request', '409 Conflict'],
    business_rules=[
        'id > 0',
        'name: 2-50 символов, буквы и дефис',
        'photoUrls: минимум 1 URL',
        'status: available|pending|sold'
    ],
    suggested_techniques=['boundary_value', 'equivalence_partitioning', 'error_guessing']
)
```

### REST API эндпоинт (GET)

```python
helper.add_analysis(
    req_id='REQ-005',
    inputs=['petId'],
    outputs=['200 OK', '400 Bad Request', '404 Not Found'],
    business_rules=[
        'petId должен быть положительным числом',
        'Время ответа <= 500ms',
        'Идемпотентный метод'
    ],
    suggested_techniques=['boundary_value', 'equivalence_partitioning']
)
```

### REST API эндпоинт (DELETE)

```python
helper.add_analysis(
    req_id='REQ-015',
    inputs=['orderId'],
    outputs=['204 No Content', '400 Bad Request', '404 Not Found'],
    business_rules=[
        'Можно удалить только placed/approved',
        'Delivered не удаляются',
        'Идемпотентная операция'
    ],
    states=['placed', 'approved', 'delivered'],
    suggested_techniques=['state_transition', 'equivalence_partitioning']
)
```

## Структура тест-кейса

Все тест-кейсы должны содержать:

```python
{
    'id': 'TC-XXX-NNN',              # Уникальный ID
    'title': 'Что тестируем',        # Короткое описание
    'priority': 'High',              # High/Medium/Low
    'test_type': 'Positive',         # Positive/Negative/Boundary/Performance
    'technique': 'boundary_value',   # Техника тест-дизайна
    'preconditions': [               # Предусловия
        'API доступен',
        'Пользователь авторизован'
    ],
    'steps': [                       # Шаги выполнения
        {'step': 1, 'action': 'Действие 1'},
        {'step': 2, 'action': 'Действие 2'}
    ],
    'expected_result': 'Что ожидаем' # Конкретный результат
}
```

## Troubleshooting

### Ошибка: "Требование не найдено"

Проверьте список требований:
```bash
./venv/bin/python main.py state show
```

### Ошибка: "Сессия не найдена"

Загрузите требования:
```bash
./venv/bin/python main.py load-demo -n petstore
```

### Некорректный формат steps

Убедитесь, что steps содержат поле `step` (номер):
```python
# Правильно
steps=[{'step': 1, 'action': 'Действие'}]

# Неправильно
steps=[{'action': 'Действие'}]
```

## Best Practices

1. **Всегда анализируйте требование перед генерацией** - это помогает выбрать правильные техники
2. **Используйте генераторы для типовых тестов** - это экономит время
3. **Группируйте тесты по требованиям** - используйте префикс REQ-XXX в TC ID
4. **Проверяйте прогресс регулярно** - `./venv/bin/python main.py state show`
5. **Экспортируйте результаты в artifacts/** - держите артефакты отдельно от кода
6. **Не забывайте mark_requirement_completed()** - это обновляет прогресс

## Дальнейшее чтение

- `src/prompts/qa_prompts.py` - промпты и примеры
- `src/utils/test_generator_helper.py` - API helper'а
- `src/state/state_manager.py` - управление состоянием
- `README.md` - общая документация проекта
