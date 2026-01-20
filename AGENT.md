# Руководство для локального CLI агента

## ⚠️ ВАЖНЫЕ ПРАВИЛА

### ЗАПРЕЩЕНО создавать новые скрипты
- **НЕ создавай** новые `.py` файлы для генерации тестов
- **НЕ пиши** собственные скрипты вместо использования существующих инструментов
- **ИСПОЛЬЗУЙ ТОЛЬКО** утилиты из `src/utils/` и CLI команды `main.py`

### ОБЯЗАТЕЛЬНО использовать только из src/utils/
Все необходимые инструменты уже есть в `src/utils/`:

**Основные утилиты:**
- **`src.utils.test_generator_helper`** - главный модуль для генерации
  - `TestGeneratorHelper` - основной класс
  - `create_boundary_test_cases()` - BVA тесты
  - `create_equivalence_test_cases()` - EP тесты
  - **🆕 `create_api_crud_test_suite()`** - полный CRUD набор
  - **🆕 `create_validation_test_cases()`** - тесты валидации
  - **🆕 `create_state_transition_tests()`** - переходы состояний
  - **🆕 `create_performance_tests()`** - тесты производительности

- **🆕 `src.utils.requirement_analyzer`** - автоматический анализатор
  - `RequirementAnalyzer.analyze()` - извлекает из текста: endpoint, метод, входы, выходы, граничные значения, состояния, техники
  - `to_helper_format()` - преобразует в формат для `add_analysis()`

**Вспомогательные:**
- **`src.utils.cleanup`** - очистка проекта
- **`src.utils.project_info`** - информация о состоянии
- **CLI `main.py`** - все операции (load, export, state)

### Правильный workflow
```bash
# ✓ Правильно: работать через Python REPL
./venv/bin/python
>>> from src.utils.test_generator_helper import TestGeneratorHelper
>>> helper = TestGeneratorHelper()
>>> pending = helper.get_pending_requirements()
>>> # генерируй тесты интерактивно для каждого требования

# ✓ Правильно: использовать CLI команды
./venv/bin/python main.py load-demo -n petstore
./venv/bin/python main.py state show
./venv/bin/python main.py state export -o artifacts/test_cases -f both

# ✗ НЕПРАВИЛЬНО: создавать файлы generate_*.py, process_*.py и т.д.
# НЕ ДЕЛАЙ ТАК! Работай только через REPL и src/utils/
```

## Главное

**Прочитай эти документы в порядке приоритета:**
1. **`WORKFLOW.md`** - полный пошаговый процесс генерации тестов с примерами кода
2. **`PROMT.md`** - полные инструкции по генерации тестов и техникам тест-дизайна

## Быстрый старт

### 1. Подготовка проекта (перед новой генерацией)

```bash
# Подготовить проект: очистить state, artifacts (с бэкапом), cache
./venv/bin/python -m src.utils.cleanup --prepare

# Без бэкапа
./venv/bin/python -m src.utils.cleanup --prepare --no-backup

# Предпросмотр (dry-run)
./venv/bin/python -m src.utils.cleanup --prepare --dry-run
```

### 2. Загрузка требований

```bash
# Из демо-файла
./venv/bin/python main.py load-demo -n petstore

# Из файла
./venv/bin/python main.py load-file requirements.md

# Из Confluence
./venv/bin/python main.py load-confluence PAGE_ID
```

### 3. Генерация тестов - АВТОМАТИЧЕСКИЙ РЕЖИМ

**⚠️ ВАЖНО: Работай ТОЛЬКО через Python REPL, НЕ создавай новые скрипты!**

#### Вариант A: Полностью автоматический анализ

Используй `RequirementAnalyzer` для автоматического извлечения параметров:

```bash
./venv/bin/python
```

```python
from src.utils.test_generator_helper import (
    TestGeneratorHelper,
    create_api_crud_test_suite,
    create_boundary_test_cases,
    create_equivalence_test_cases,
    create_state_transition_tests
)
from src.utils.requirement_analyzer import RequirementAnalyzer

helper = TestGeneratorHelper()
analyzer = RequirementAnalyzer()

# Получить необработанные требования
pending = helper.get_pending_requirements()
print(f"Необработано: {len(pending)} требований")

# Для каждого требования:
for req_info in pending:
    req_id = req_info['id']
    req_text = helper.get_requirement_text(req_id)
    
    # 🆕 АВТОМАТИЧЕСКИЙ АНАЛИЗ
    analysis = analyzer.analyze(req_text, req_id)
    
    # Добавить анализ
    helper_params = analyzer.to_helper_format(analysis)
    helper.add_analysis(req_id=req_id, **helper_params)
    
    # 🆕 Автоматически создать CRUD тесты
    crud_tests = create_api_crud_test_suite(
        req_id=req_id,
        base_tc_id=f'TC-{req_id.split("-")[1]}',
        endpoint=analysis.endpoint,
        http_method=analysis.http_method,
        req_type=analysis.requirement_type,
        preconditions=['API доступен']
    )
    helper.add_test_cases_bulk(req_id, crud_tests)
    
    # 🆕 Автоматически создать BVA тесты из граничных значений
    for field, bounds in analysis.boundary_values.items():
        bva_tests = create_boundary_test_cases(
            req_id=req_id,
            base_tc_id=f'TC-{req_id.split("-")[1]}-{field.upper()}',
            field_name=field,
            min_value=bounds['min'],
            max_value=bounds['max'],
            valid_example=(bounds['min'] + bounds['max']) // 2,
            invalid_low=bounds['min'] - 1,
            invalid_high=bounds['max'] + 1,
            endpoint=analysis.endpoint
        )
        helper.add_test_cases_bulk(req_id, bva_tests)
    
    # 🆕 Автоматически создать EP тесты из классов эквивалентности
    for field, classes in analysis.equivalence_classes.items():
        ep_tests = create_equivalence_test_cases(
            req_id=req_id,
            base_tc_id=f'TC-{req_id.split("-")[1]}-{field.upper()}',
            field_name=field,
            valid_values=classes['valid'],
            invalid_values=classes['invalid'],
            endpoint=analysis.endpoint
        )
        helper.add_test_cases_bulk(req_id, ep_tests)
    
    # Завершить
    helper.mark_requirement_completed(req_id)
    print(f"✓ {req_id} завершено")

# Статистика
stats = helper.get_statistics()
print(f"Завершено: {stats['completed_requirements']}/{stats['total_requirements']}")
print(f"Всего тестов: {stats['total_test_cases']}")
```

#### Вариант B: Ручной анализ (если автоматический не подходит)

```python
from src.utils.test_generator_helper import (
    TestGeneratorHelper,
    create_boundary_test_cases,
    create_equivalence_test_cases
)

helper = TestGeneratorHelper()
pending = helper.get_pending_requirements()

for req_info in pending:
    req_id = req_info['id']
    
    # Ручной анализ требования
    helper.add_analysis(
        req_id=req_id,
        inputs=['id', 'name'],
        outputs=['201 Created', '400 Bad Request'],
        business_rules=['id > 0', 'name: 2-50 символов'],
        suggested_techniques=['boundary_value', 'equivalence_partitioning']
    )
    
    # Создать тесты с генераторами
    bva_tests = create_boundary_test_cases(
        req_id=req_id,
        base_tc_id=f'TC-{req_id.split("-")[1]}',
        field_name='quantity',
        min_value=1,
        max_value=100,
        valid_example=50,
        invalid_low=0,
        invalid_high=101,
        endpoint='POST /store/order'
    )
    helper.add_test_cases_bulk(req_id, bva_tests)
    
    # Завершить
    helper.mark_requirement_completed(req_id)
```

### 4. Доступные генераторы тестов

Все генераторы находятся в `src.utils.test_generator_helper`:

#### 🆕 create_api_crud_test_suite()
Автоматически создает полный набор CRUD тестов:
- **create**: успешное создание, дубликат ID, отсутствие обязательных полей
- **read**: успешное получение, несуществующий объект, невалидный ID
- **update**: успешное обновление, несуществующий объект, невалидные данные
- **delete**: успешное удаление, несуществующий объект, идемпотентность
- **search**: поиск с результатами, пустой результат, невалидные параметры

```python
crud_tests = create_api_crud_test_suite(
    req_id='REQ-001',
    base_tc_id='TC-001',
    endpoint='/pet',
    http_method='POST',
    req_type='create',  # 'create', 'read', 'update', 'delete', 'search'
    preconditions=['API доступен']
)
```

#### create_boundary_test_cases()
Граничные значения (BVA):
```python
bva_tests = create_boundary_test_cases(
    req_id='REQ-003',
    base_tc_id='TC-003',
    field_name='quantity',
    min_value=1,
    max_value=100,
    valid_example=50,
    invalid_low=0,
    invalid_high=101,
    endpoint='POST /store/order'
)
```

#### create_equivalence_test_cases()
Классы эквивалентности (EP):
```python
ep_tests = create_equivalence_test_cases(
    req_id='REQ-003',
    base_tc_id='TC-003',
    field_name='status',
    valid_values=['available', 'pending', 'sold'],
    invalid_values=['unknown', 'deleted'],
    endpoint='POST /pet'
)
```

#### 🆕 create_validation_test_cases()
Тесты валидации полей:
```python
val_tests = create_validation_test_cases(
    req_id='REQ-001',
    base_tc_id='TC-001',
    endpoint='/user',
    http_method='POST',
    fields_validation={
        'email': 'формат email',
        'phone': 'формат телефона',
        'password': 'минимум 8 символов, обязательное'
    }
)
```

#### 🆕 create_state_transition_tests()
Переходы состояний:
```python
st_tests = create_state_transition_tests(
    req_id='REQ-007',
    base_tc_id='TC-007',
    endpoint='/store/order/{orderId}',
    http_method='DELETE',
    valid_transitions=[
        ('placed', 'cancelled'),
        ('approved', 'cancelled')
    ],
    invalid_transitions=[
        ('delivered', 'cancelled'),
        ('cancelled', 'placed')
    ]
)
```

#### 🆕 create_performance_tests()
Базовые тесты производительности:
```python
perf_tests = create_performance_tests(
    req_id='REQ-002',
    base_tc_id='TC-002',
    endpoint='/pet/{petId}',
    http_method='GET',
    max_response_time_ms=500
)
```

### 5. Экспорт результатов

```bash
# В Excel и CSV
./venv/bin/python main.py state export -o artifacts/test_cases -f both

# Только Excel
./venv/bin/python main.py state export -o artifacts/test_cases -f excel
```

## Вспомогательные команды

### Полный pipeline для raw-требований

```bash
./venv/bin/python main.py agent pipeline-raw --agent codex --dir requirements/raw --yes
```

### Полный pipeline для demo-требований

```bash
./venv/bin/python main.py agent pipeline-demo --agent codex --name petstore --yes
```

Варианты:

```bash
# Qwen
./venv/bin/python main.py agent pipeline-demo --agent qwen --name petstore --yes

# Claude
./venv/bin/python main.py agent pipeline-demo --agent claude --name petstore --yes

# Без бэкапа artifacts
./venv/bin/python main.py agent pipeline-demo --agent codex --name petstore --no-backup --yes

# С подтверждением (без --yes)
./venv/bin/python main.py agent pipeline-demo --agent codex --name petstore
```

### Управление состоянием

```bash
# Показать текущее состояние
./venv/bin/python main.py state show

# Что делать дальше
./venv/bin/python main.py state resume

# Полный контекст для восстановления
./venv/bin/python main.py state context

# Создать новую сессию
./venv/bin/python main.py state new --agent local_agent
```

### Информация о проекте

```bash
# Информация о структуре
./venv/bin/python main.py info

# Доступные техники тест-дизайна
./venv/bin/python main.py techniques

# Промпт для внешнего CLI агента (опционально)
./venv/bin/python main.py agent-prompt

# Детальная информация (JSON)
./venv/bin/python -m src.utils.project_info --format json
```

### Очистка

```bash
# Подготовка к новой генерации (рекомендуется)
./venv/bin/python -m src.utils.cleanup --prepare

# Только state файлы
./venv/bin/python -m src.utils.cleanup --state-only

# Только кэш
./venv/bin/python -m src.utils.cleanup --cache-only

# Все включая exports
./venv/bin/python -m src.utils.cleanup --all

# Предпросмотр
./venv/bin/python -m src.utils.cleanup --dry-run
```

## Структура проекта

```
ai-test-generator/
├── src/
│   ├── agents/          # Модели данных для тестов
│   ├── generators/      # Экспорт в Excel/CSV
│   ├── parsers/         # Парсеры Confluence
│   ├── prompts/         # QA промпты и инструкции
│   ├── state/           # State Manager
│   └── utils/
│       ├── test_generator_helper.py  # ← Главный helper для генерации
│       ├── cleanup.py               # ← Подготовка проекта
│       ├── project_info.py          # Информация о проекте
│       └── logger.py                # Логирование
├── demo/
│   └── petstore.md      # Демо требования
├── artifacts/           # Экспортированные результаты
├── WORKFLOW.md          # ← ПОДРОБНЫЙ WORKFLOW с примерами
├── PROMT.md             # Промпты и техники
└── test_generation_demo.py  # Полный пример генерации
```

## Демо-скрипт

Полный пример автоматической генерации:

```bash
./venv/bin/python test_generation_demo.py
```

Показывает:
- Загрузку требований
- Анализ
- Генерацию с BVA/EP шаблонами
- Добавление ручных тестов
- Статистику

## Troubleshooting

### "Требование не найдено"
```bash
./venv/bin/python main.py state show  # Проверить список
```

### "Сессия не найдена"
```bash
./venv/bin/python main.py load-demo -n petstore
```

### Некорректный формат steps
```python
# ✓ Правильно
steps=[{'step': 1, 'action': 'Действие'}]

# ✗ Неправильно
steps=[{'action': 'Действие'}]
```

## Дополнительная документация

- **WORKFLOW.md** - пошаговый процесс с примерами кода ← НАЧНИ ОТСЮДА
- **PROMT.md** - полные инструкции по генерации
- **README.md** - общая информация о проекте
- **src/prompts/qa_prompts.py** - промпты и техники
- **src/utils/test_generator_helper.py** - API helper'а
