# AI Test Generator

**AI Test Generator** - инструмент для автоматической генерации тест-кейсов на основе требований с использованием современных техник тест-дизайна и CLI агентов (Claude Code, Qwen Code, Cursor).

## Возможности

- Загрузка требований из Confluence или текстовых файлов
- Генерация тест-кейсов с использованием признанных техник:
  - Equivalence Partitioning (Эквивалентное разбиение)
  - Boundary Value Analysis (Анализ граничных значений)
  - Decision Table (Таблицы решений)
  - State Transition (Переходы состояний)
  - Use Case Testing (Варианты использования)
  - Pairwise Testing (Попарное тестирование)
  - Error Guessing (Предугадывание ошибок)
- State Manager для сохранения контекста между сессиями
- Экспорт результатов в Excel и CSV
- CLI интерфейс для работы с агентами

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

### 4. Настройка конфигурации

Скопируйте файл `.env.example` в `.env` и заполните необходимые параметры:

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

## Быстрый старт

### Для CLI агентов (Claude Code, Qwen Code, Cursor)

1. Проверьте текущее состояние:
```bash
python3 main.py state show
```

2. Создайте новую сессию:
```bash
python3 main.py state new --agent claude_code
```

3. Посмотрите, что делать дальше:
```bash
python3 main.py state resume
```

4. Получите полный контекст для восстановления:
```bash
python3 main.py state context
```

Подробное руководство для CLI агентов смотрите в [PROMT.md](PROMT.md) или [AGENT.md](AGENT.md).

### Загрузка требований

#### Из файла

```bash
python3 main.py load-file requirements.txt
```

#### Из Confluence

```bash
python3 main.py load-confluence PAGE_ID
```

#### Демо-требования

```bash
python3 main.py load-demo --name petstore
```

### Экспорт результатов

```bash
# Экспорт в Excel
python3 main.py state export -f excel -o test_cases

# Экспорт в CSV
python3 main.py state export -f csv -o test_cases

# Экспорт в оба формата
python3 main.py state export -f both -o test_cases
```

## CLI Команды

### Основные команды

```bash
# Показать доступные техники тест-дизайна
python3 main.py techniques

# Показать промпт для CLI агента
python3 main.py agent-prompt

# Показать информацию о проекте
python3 main.py info
```

### State Manager

```bash
# Показать состояние
python3 main.py state show
python3 main.py state show -f json

# Создать новую сессию
python3 main.py state new -a claude_code

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
│   ├── generators/      # Генерация и экспорт тестов
│   ├── parsers/         # Парсеры (Confluence)
│   ├── prompts/         # Промпты для генерации тестов
│   ├── state/           # State Manager
│   └── utils/           # Утилиты (логирование, info)
├── main.py              # CLI интерфейс
├── AGENT.md             # Руководство для CLI агентов
├── WORKFLOW.md          # Пошаговый процесс генерации
├── PROMT.md             # Промпты и инструкции
├── requirements.txt     # Зависимости
└── .env.example         # Пример конфигурации
```

## Техники тест-дизайна

### 1. Equivalence Partitioning (Эквивалентное разбиение)

Разделение входных данных на классы эквивалентности. Применяется когда есть классы входных данных.

### 2. Boundary Value Analysis (Анализ граничных значений)

Тестирование значений на границах диапазонов. Применяется когда есть диапазоны значений.

### 3. Decision Table (Таблицы решений)

Тестирование комбинаций условий и действий. Применяется для комбинаций условий.

### 4. State Transition (Переходы состояний)

Тестирование переходов между состояниями системы. Применяется для объектов со статусами.

### 5. Use Case Testing (Варианты использования)

Тестирование сценариев использования. Применяется для пользовательских сценариев.

### 6. Pairwise Testing (Попарное тестирование)

Минимальный набор тестов для покрытия пар значений. Применяется когда много параметров.

### 7. Error Guessing (Предугадывание ошибок)

Тесты на основе типичных ошибок и опыта. Применяется всегда дополнительно.

## State Management

State Manager - ключевая особенность проекта, которая предотвращает:

- Потерю контекста между сессиями
- Галлюцинации агентов (есть "источник истины")
- Дублирование работы (видно что уже сделано)
- Несогласованность данных

Все операции с требованиями и тест-кейсами должны проходить через State Manager.

### Development

Для разработки и отладки достаточно запускать CLI команды и демо-скрипт:

```bash
python3 main.py info
./venv/bin/python test_generation_demo.py
```

### Структура State файла

State Manager сохраняет состояние в `.test_generator_state.json`:

```json
{
  "session_id": "20260114_153022",
  "agent_type": "claude_code",
  "progress": {
    "total_requirements": 5,
    "processed_requirements": 3,
    "current_step": "generating"
  },
  "requirements": [
    {
      "id": "REQ-001",
      "status": "completed",
      "test_cases": []
    }
  ]
}
```

**Не редактируйте этот файл вручную!** Используйте StateManager API.

## Документация

- [PROMT.md](PROMT.md) - Полное руководство для CLI агентов
- [AGENT.md](AGENT.md) - Краткая справка для агентов
- [Wiki](wiki/) - Детальная документация по компонентам

## Требования

- Python 3.10+
- Зависимости из `requirements.txt`

## Лицензия

MIT

## Контакты

При возникновении вопросов создайте issue в репозитории.
