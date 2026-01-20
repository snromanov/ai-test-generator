# AI Test Generator

**AI Test Generator** - CLI-first инструмент для работы с требованиями, сохранения состояния и экспорта тест-кейсов. Генерацию выполняет локальный CLI агент на базе встроенных утилит и State Manager.

## Диаграмма компонентов

![AI Test Generator UML (Component)](https://www.plantuml.com/plantuml/svg/LLJBRjim4BphAmYVaeFiFoWY2Af3G8u5IJ4A58N1ockL2KKg8WN4BVhlNL9Q9hsDTcOVd5txmJenkNbGYPDE0SiuQy4wjWSDat1cOYbxFfJiBZV3Q3HeTv_yaXTWri44njr6i4aoYkvLzC0sKMKtx4_2sFT1IBqTRp-Oi2mlkG_v-bcF6dOtc0ieUn_OxE39Qi8AphAxDx6RvKwfOM6h-dYeseRoSs4XZXW4RRxtPEE4WuFGECqIRmvBU9exDqzmgU5jbXCCsByIaoLLNL7fMFOHrBZIxVxHqvzoCotKxVTArvbdSwElQWRTmQV2UQXRl8zcGiFmNSLx1sgNDwVbNSMt8CWL23sFgqrFgnClq3ckhsPn89Z7zJYxar3o8fmqEZ3yv9dIzFJcyXYyiD3DatGtyhyfyX2sq_KyJiPXTImHsQR-wcbyEvoL72JEIrnTXaJlxLbg1_r_PVddPcU5SqZTHzQduh3Y9wwCRROEBJxtvF4vrDo-MACtGTrcRO49LwcyMCZKwrFKfrRsMlWLfgzmMyHy7wNHri0SdrjaEcNcYxz9sWlBAXxu_FZatoewV-0Rl4iM3Z9msRvuQfE_IUB3QVebN1PXl2Q2T96HmXCYZ0SHi_5q2FlDndGU8UwF8Fu84kotgAi8iIr1Vp24CP6WNtc2lQ9yXJvUPt6I5GPrNYrYl_SLuvvN51mYHOo6lEQmHF6Q2792E175mYQZO1zXIIWKm-U43xynmcW2mQLXaSTK79PmNSOe9yHFCGtDZhZY4UAQ8iu-1bctIQj9mXMmxVPZpnyHR-G3w8l_r_m7)

## Возможности

- Загрузка требований из Confluence или текстовых файлов
- Управление состоянием сессии (источник истины для агента)
- Поддержка техник тест-дизайна ISTQB (для использования в промптах агента):
  - Equivalence Partitioning (Эквивалентное разбиение)
  - Boundary Value Analysis (Анализ граничных значений)
  - Decision Table (Таблицы решений)
  - State Transition (Переходы состояний)
  - Use Case Testing (Варианты использования)
  - Pairwise Testing (Попарное тестирование)
  - Error Guessing (Предугадывание ошибок)
- Экспорт результатов в Excel и CSV

## Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd ai-test-generator
```

### 2. Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

Важно: все команды ниже предполагают активированное виртуальное окружение `venv`.

### 4. Настройка конфигурации (опционально для Confluence)

```bash
cp .env.example .env
```

Отредактируйте `.env`:

```ini
# Confluence Configuration (опционально)
CONFLUENCE_URL=https://your-company.atlassian.net/wiki
CONFLUENCE_USER=your-email@company.com
CONFLUENCE_TOKEN=your-confluence-api-token

# Logging
LOG_LEVEL=INFO
```

## Быстрый старт (демо)

1. Создайте новую сессию:
```bash
python3 main.py state new --agent local_agent
```

2. Загрузите демо-требования:
```bash
python3 main.py load-demo --name petstore
```

3. Запустите локальный агент (автопоток):
```bash
python3 - <<'PY'
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
        if isinstance(bounds.get("min"), int) and isinstance(bounds.get("max"), int):
            bva_tests = create_boundary_test_cases(
                req_id=req_id,
                base_tc_id=f"{base_tc_id}-{field.upper()}",
                field_name=field,
                min_value=bounds["min"],
                max_value=bounds["max"],
                valid_example=(bounds["min"] + bounds["max"]) // 2,
                invalid_low=bounds["min"] - 1,
                invalid_high=bounds["max"] + 1,
                endpoint=analysis.endpoint or "N/A",
            )
            helper.add_test_cases_bulk(req_id, bva_tests)

    for field, classes in analysis.equivalence_classes.items():
        ep_tests = create_equivalence_test_cases(
            req_id=req_id,
            base_tc_id=f"{base_tc_id}-{field.upper()}",
            field_name=field,
            valid_values=classes.get("valid", []),
            invalid_values=classes.get("invalid", []),
            endpoint=analysis.endpoint or "N/A",
        )
        helper.add_test_cases_bulk(req_id, ep_tests)

    helper.mark_requirement_completed(req_id)
PY
```

4. Экспортируйте результаты:
```bash
python3 main.py state export -f excel -o test_cases
```

Подробное руководство: [AGENT.md](AGENT.md) | [WORKFLOW.md](WORKFLOW.md)

## Старт с нуля (проект пустой)

1. Создайте виртуальное окружение и установите зависимости:
```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

2. Положите сырые требования в `requirements/raw/` (файлы `.md` или `.txt`).

3. Запустите полный pipeline для raw-требований выбранным агентом:
```bash
./venv/bin/python main.py agent pipeline-raw --agent codex --dir requirements/raw --yes
```

4. Проверьте состояние и экспортируйте результаты:
```bash
./venv/bin/python main.py state show
./venv/bin/python main.py state export -f excel -o artifacts/test_cases
```

## Подробный guide: где смотреть тесты

### 1) Пересобрать state и подготовить тесты
```bash
./venv/bin/python main.py rebuild-raw --dir requirements/raw
```

### 2) Посмотреть тесты в state (текстовый вывод)
```bash
./venv/bin/python main.py state show
```

### 3) Где физически хранятся тесты
Тесты сохраняются внутри state-файла в корне проекта:
- `.test_generator_state.json`

### 4) Экспорт в Excel/CSV (чтобы получить файлы)
```bash
./venv/bin/python main.py state export -f excel -o artifacts/test_cases
# или
./venv/bin/python main.py state export -f csv -o artifacts/test_cases
```

### 5) Где искать экспортированные файлы
После экспорта файлы будут в `artifacts/`:
- `artifacts/test_cases.xlsx`
- `artifacts/test_cases.csv`

### 6) Частые причины, почему «не видно тестов»
- Не запускали `state show`
- Не делали экспорт `state export`
- State очищен после `rebuild-raw`

## Flow: сырые требования → подготовка тестов

1. Сложите сырые требования в `requirements/raw/` (файлы `.md` или `.txt`).
   Можно использовать теги `[Back]`, `[Front]`, `[API]`, `[UI]` и разделитель `---`.

2. Загрузите требования в state:
```bash
python3 main.py load-raw --dir requirements/raw
```

3. Посмотрите, что загрузилось:
```bash
python3 main.py state show
```

4. Подготовьте анализ и тесты через REPL (без новых скриптов):
```bash
./venv/bin/python
```
```python
from src.utils.test_generator_helper import TestGeneratorHelper
from src.utils.requirement_analyzer import RequirementAnalyzer

helper = TestGeneratorHelper()
analyzer = RequirementAnalyzer()

for req in helper.get_pending_requirements():
    req_id = req["id"]
    req_text = helper.get_requirement_text(req_id)
    analysis = analyzer.analyze(req_text, req_id)
    helper.add_analysis(req_id=req_id, **analyzer.to_helper_format(analysis))
```

5. Экспортируйте результаты:
```bash
python3 main.py state export -f excel -o artifacts/test_cases
```

## Загрузка требований

```bash
# Из файла требований
python3 main.py load-file requirements.md

# Из папки с сырыми требованиями (.md/.txt)
python3 main.py load-raw --dir requirements/raw

# Из Confluence
python3 main.py load-confluence PAGE_ID

# Демо-требования
python3 main.py load-demo --name petstore
```

## Полный reset + подготовка

Команда очищает state/кэш, делает бэкап `artifacts` (по умолчанию),
заново читает сырые требования и готовит базовые тест-кейсы.

```bash
python3 main.py agent pipeline-raw --agent codex --dir requirements/raw --yes
```

Это и есть запуск локального агента для raw‑pipeline. Агент указывается через `--agent`.

### Варианты pipeline-raw

```bash
# Codex
python3 main.py agent pipeline-raw --agent codex --dir requirements/raw --yes

# Qwen
python3 main.py agent pipeline-raw --agent qwen --dir requirements/raw --yes

# Claude
python3 main.py agent pipeline-raw --agent claude --dir requirements/raw --yes

# Без авто-детекта layer/component
python3 main.py agent pipeline-raw --agent codex --dir requirements/raw --no-auto-detect --yes

# Без бэкапа artifacts
python3 main.py agent pipeline-raw --agent codex --dir requirements/raw --no-backup --yes

# С подтверждением (без --yes)
python3 main.py agent pipeline-raw --agent codex --dir requirements/raw
```

### Варианты pipeline-demo

```bash
# Codex
python3 main.py agent pipeline-demo --agent codex --name petstore --yes

# Qwen
python3 main.py agent pipeline-demo --agent qwen --name petstore --yes

# Claude
python3 main.py agent pipeline-demo --agent claude --name petstore --yes

# Без бэкапа artifacts
python3 main.py agent pipeline-demo --agent codex --name petstore --no-backup --yes

# С подтверждением (без --yes)
python3 main.py agent pipeline-demo --agent codex --name petstore
```

### Формат файла требований

Требования должны быть достаточно длинными (50+ символов). Разделяйте их пустой строкой.

Пример `requirements.md`:

```
Система должна разрешать регистрацию пользователя по email и паролю,
валидируя пароль минимум 8 символов.

После успешной регистрации система отправляет письмо с подтверждением
на указанный адрес и помечает аккаунт как неактивный.
```

## Экспорт результатов

```bash
# Экспорт в Excel
python3 main.py state export -f excel -o test_cases

# Экспорт в CSV
python3 main.py state export -f csv -o test_cases

# Экспорт в оба формата
python3 main.py state export -f both -o test_cases
```

## CLI команды

### Основные команды

```bash
# Показать доступные техники тест-дизайна
python3 main.py techniques

# Показать промпт для внешнего CLI агента (опционально)
python3 main.py agent-prompt

# Полный pipeline для raw-требований
python3 main.py agent pipeline-raw --agent codex --dir requirements/raw --yes

# Показать информацию о проекте
python3 main.py info
```

### State Manager

```bash
# Показать состояние
python3 main.py state show
python3 main.py state show -f json

# Создать новую сессию
python3 main.py state new -a local_agent

# Добавить требование
python3 main.py state add "Текст требования"

# Получить контекст
python3 main.py state context

# Что делать дальше
python3 main.py state resume

# Добавить заметку
python3 main.py state note "Важная заметка"

# Экспорт результатов
python3 main.py state export -o tests -f excel

# Очистить состояние
python3 main.py state clear
```

## Структура проекта

```
ai-test-generator/
├── src/
│   ├── agents/          # Модели данных для тест-кейсов
│   ├── generators/      # Загрузка требований и экспорт
│   ├── parsers/         # Парсеры (Confluence)
│   ├── prompts/         # Промпты для генерации тестов
│   ├── state/           # State Manager
│   └── utils/           # Утилиты
├── requirements/
│   └── raw/             # Сырые требования (.md/.txt)
├── scripts/             # Вспомогательные скрипты
├── main.py              # CLI интерфейс
├── ARCHITECTURE.md      # Архитектура (ASCII диаграммы)
├── UML.puml             # PlantUML диаграммы
├── SECURITY.md          # Документация по безопасности
├── AGENT.md             # Руководство для CLI агентов
├── WORKFLOW.md          # Пошаговый процесс генерации
├── PROMT.md             # Промпты и инструкции
├── requirements.txt     # Зависимости
└── .env.example         # Пример конфигурации
```

## Документация

| Документ | Описание |
|----------|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Архитектура, диаграммы, паттерны |
| [SECURITY.md](SECURITY.md) | Безопасность, OWASP, аудит |
| [AGENT.md](AGENT.md) | Руководство для CLI агентов |
| [WORKFLOW.md](WORKFLOW.md) | Пошаговый процесс генерации |
| [PROMT.md](PROMT.md) | Промпты и инструкции |

## Требования

- Python 3.10+
- Зависимости из `requirements.txt`

## Development

```bash
# Информация о проекте
python3 main.py info

# Демо генерация (без внешнего агента)
python3 generate_demo_tests.py
```

## Лицензия

MIT

## Контакты

При возникновении вопросов создайте issue в репозитории.
