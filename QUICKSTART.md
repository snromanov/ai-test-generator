# Быстрый старт - AI Test Generator

## Установка

```bash
# Клонировать проект
git clone <repository-url>
cd ai-test-generator

# Создать виртуальное окружение
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

# Установить зависимости
pip install -r requirements.txt
```

## Быстрый запуск - 3 источника требований

### 1️⃣ Demo (готовый пример PetStore API)

**Самый быстрый способ проверить инструмент:**

```bash
# Вариант 1: через скрипт (рекомендуется)
./generate_tests.py --source demo/petstore

# Вариант 2: через main.py
python main.py generate --source demo/petstore

# Результат: 8 требований → 63 тест-кейса за 1 секунду
```

Файл с требованиями: `demo/petstore.md`

**Что получите:**
- `artifacts/test_cases.xlsx` - 63 готовых тест-кейса
- Группировка по слоям (API)
- BVA, EP, LLM integration тесты

---

### 2️⃣ Raw (ваши требования из requirements/raw/)

**Для работы с вашими требованиями:**

```bash
# Шаг 1: Положите файлы в requirements/raw/
# Поддерживаются файлы: *.md, *.txt

# Шаг 2: Запустите генерацию
./generate_tests.py --source raw

# Или просто (raw - источник по умолчанию)
./generate_tests.py

# С кастомной папкой
python main.py generate --source requirements/my_custom_folder
```

**Формат файлов:**

```markdown
# requirements/raw/my_app.md

API должен возвращать список пользователей с пагинацией. 
Параметры: limit (10-100), offset (0+).

---

Форма регистрации должна содержать поля email и пароль (минимум 8 символов).

---

[API] [Back]
## Создание заказа
Система должна создавать заказ с валидацией количества товара (1-100 единиц).
```

**Поддерживаемые теги (опционально):**
- `[API]`, `[UI]`, `[Integration]`, `[E2E]` - слои
- `[Back]`, `[Front]`, `[Fullstack]` - компоненты

**Результат:**
- Автоматическое определение layer/component (если нет тегов)
- BVA для числовых полей (limit, offset, пароль)
- EP для статусов/перечислений
- UI тесты (календари, загрузка файлов)
- Экспорт с группировкой по слоям

---

### 3️⃣ Confluence (загрузка из Confluence Cloud/Server)

**Для работы с Confluence:**

```bash
# Шаг 1: Настройте .env
cp .env.example .env
# Отредактируйте .env:
#   CONFLUENCE_URL=https://your-company.atlassian.net/wiki
#   CONFLUENCE_USER=your-email@company.com
#   CONFLUENCE_TOKEN=your-api-token

# Шаг 2: Запустите генерацию (укажите PAGE_ID из URL)
./generate_tests.py --source confluence:123456789

# Пример URL: https://company.atlassian.net/wiki/spaces/PROJ/pages/123456789/Requirements
#                                                                    ^^^^^^^^^ это PAGE_ID
```

**Как получить API Token:**
1. Откройте https://id.atlassian.com/manage-profile/security/api-tokens
2. Создайте новый токен
3. Скопируйте и вставьте в `.env`

**Результат:**
- Автоматическое извлечение требований из HTML
- Санитизация (защита от XSS, prompt injection)
- Генерация тестов как для raw

---

## Сравнение источников

| Источник | Когда использовать | Команда | Время |
|----------|-------------------|---------|-------|
| **demo** | Быстрая проверка, знакомство | `./generate_tests.py --source demo/petstore` | 1 сек |
| **raw** | Основная работа, локальные файлы | `./generate_tests.py --source raw` | 1-5 сек |
| **confluence** | Интеграция с командой, централизованное хранилище | `./generate_tests.py --source confluence:PAGE_ID` | 2-10 сек |

---

## Дополнительные возможности

### Генерация из конкретного файла

```bash
# Из любого файла в проекте
./generate_tests.py --source path/to/requirements.md

# Из файла вне проекта (абсолютный путь)
./generate_tests.py --source /home/user/docs/specs.txt
```

### Форматы экспорта

```bash
# Excel (по умолчанию, с группировкой по слоям)
./generate_tests.py --source demo/petstore --format excel

# CSV (простой формат)
./generate_tests.py --source demo/petstore --format csv

# Allure TestOps (CSV для импорта в Allure)
./generate_tests.py --source demo/petstore --format allure

# Оба формата сразу (Excel + CSV)
./generate_tests.py --source demo/petstore --format both

# Кастомное имя выходного файла
./generate_tests.py --source demo/petstore --output my_project_tests
```

### Экспорт для Allure TestOps

Формат `allure` создает CSV-файл, полностью совместимый с импортом в Allure TestOps:

```bash
# Базовый экспорт
./generate_tests.py --source raw --format allure

# С метаданными Allure
./generate_tests.py --source raw --format allure \
  --allure-suite "Мой проект" \
  --allure-feature "Авторизация" \
  --allure-epic "MVP" \
  --allure-owner "username" \
  --allure-jira "https://jira.company.com/browse/PROJ-123"

# Экспорт существующих тестов в Allure формат
python main.py export -f allure --allure-suite "календарь"
```

**Формат Allure CSV:**
- Разделитель: `;` (точка с запятой)
- Сценарий: `[step N]` для шагов, `[expected N.1]` для результатов
- Поддерживает: Suite, Feature, Epic, Owner, Jira, теги

**Импорт в Allure TestOps:**
1. Перейдите в раздел "Тест-кейсы"
2. Нажмите "Импорт" → выберите CSV файл
3. Включите "Показывать заголовки" и "Автоопределение формата"
4. Настройте маппинг полей (name → Название, scenario → Сценарий, и т.д.)

### Полная команда с опциями

```bash
./generate_tests.py \
  --source requirements/raw \
  --output artifacts/my_tests \
  --format excel \
  --agent local_agent \
  --no-backup
```

**Доступные флаги:**

| Флаг | Описание | По умолчанию |
|------|----------|--------------|
| `--source` | Источник требований (raw, demo/petstore, file.md, confluence:ID) | `raw` |
| `--output` | Имя выходного файла (без расширения) | `artifacts/test_cases` |
| `--format` | Формат экспорта (excel, csv, allure, both) | `excel` |
| `--agent` | Тип агента (local_agent, codex, qwen, claude) | `local_agent` |
| `--no-backup` | Не создавать бэкап artifacts | false |
| `--no-clean` | Не очищать state перед генерацией | false |
| `--no-group` | Не группировать по слоям в Excel | false |
| `--no-auto-detect` | Не определять layer/component автоматически | false |
| `--allure-suite` | Suite для Allure TestOps | - |
| `--allure-feature` | Feature для Allure TestOps | - |
| `--allure-epic` | Epic для Allure TestOps | - |
| `--allure-owner` | Owner для Allure TestOps | - |
| `--allure-jira` | Jira link для Allure TestOps | - |

---

---

## Что происходит при выполнении?

Команда `generate` выполняет полный цикл за 4 шага:

```
┌─────────────────────────────────────────────────┐
│ Шаг 1/4: Подготовка проекта                     │
├─────────────────────────────────────────────────┤
│ ✓ Бэкап artifacts → artifacts_backup_TIMESTAMP   │
│ ✓ Очистка .test_generator_state.json            │
│ ✓ Очистка __pycache__                           │
│ ✓ Создание новой сессии                         │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Шаг 2/4: Загрузка требований                    │
├─────────────────────────────────────────────────┤
│ ✓ Чтение файлов из источника                    │
│ ✓ Парсинг структурированных требований          │
│ ✓ Автоопределение layer (api/ui) и component    │
│ ✓ Сохранение в state                            │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Шаг 3/4: Анализ и генерация тест-кейсов         │
├─────────────────────────────────────────────────┤
│ ✓ RequirementAnalyzer:                          │
│   • Определение входов/выходов                  │
│   • Граничные значения (min/max)                │
│   • Классы эквивалентности (valid/invalid)      │
│   • Детекция паттернов (API, UI, LLM)           │
│ ✓ TestGeneratorHelper:                          │
│   • BVA тесты для числовых полей                │
│   • EP тесты для перечислений/статусов          │
│   • UI тесты (calendar, file upload)            │
│   • Integration тесты (LLM, API)                │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Шаг 4/4: Экспорт результатов                    │
├─────────────────────────────────────────────────┤
│ ✓ Конвертация state → GenerationResult          │
│ ✓ Группировка по слоям (API/UI/Integration/E2E) │
│ ✓ Экспорт в Excel с форматированием             │
│ ✓ Опционально: экспорт в CSV                    │
└─────────────────────────────────────────────────┘
```

**Время выполнения:**
- Demo (8 требований): ~1 секунда
- Raw (20 требований): ~2-3 секунды
- Confluence (50 требований): ~5-10 секунд

---

## Результат

После выполнения вы получите:

```
artifacts/
  ├── test_cases.xlsx    # Готовые тест-кейсы
  └── ...

artifacts_backup_*/      # Бэкап предыдущих результатов
```

Excel файл содержит:
- Группировку по слоям (API, UI, Integration, E2E)
- Детальные шаги тестирования
- Ожидаемые результаты
- Приоритеты
- Техники тест-дизайна

## Примеры использования

### Пример 1: Быстрая проверка на demo

```bash
./generate_tests.py --source demo/petstore --output demo_results
```

**Вывод:**
```
=== AI Test Generator ===

Источник: demo/petstore
Агент: local_agent
Формат: excel

=== Результаты генерации ===

✓ Загружено требований: 8
✓ Сгенерировано тестов: 63

Статистика по слоям:
  API: 8

Статистика по компонентам:
  Fullstack: 8

Экспортированные файлы:
  artifacts/demo_results.xlsx

✓ Генерация завершена успешно!
```

**Результат:** 8 требований → 63 тест-кейса за 1 секунду

---

### Пример 2: Генерация из своих требований (raw)

```bash
# Шаг 1: Создайте файл requirements/raw/my_app.md
cat > requirements/raw/my_app.md << 'EOF'
API должен возвращать список пользователей с пагинацией. 
Параметры: limit (10-100), offset (0+). Время ответа не более 500ms.

---

Форма регистрации должна валидировать email и требовать пароль длиной 8-50 символов.

---

[UI] [Front]
## Загрузка фотографий профиля
Пользователь может загрузить до 5 фотографий в формате JPG/PNG, размером не более 10 МБ каждая.
EOF

# Шаг 2: Запустите генерацию
./generate_tests.py --source raw --output my_app_tests --format both

# Шаг 3: Проверьте результаты
ls -lh artifacts/my_app_tests.*
```

**Результат:**
- `artifacts/my_app_tests.xlsx` - Excel с группировкой по слоям (API, UI)
- `artifacts/my_app_tests.csv` - CSV для импорта в TestRail/Jira
- BVA тесты для limit (10, 11, 99, 100, 101), offset (0, 1, -1)
- EP тесты для email (valid, invalid), password (< 8, 8, 50, > 50)
- UI тесты для загрузки файлов (формат, размер, количество)

---

### Пример 3: Confluence + кастомные настройки

```bash
# Настройте .env (один раз)
echo "CONFLUENCE_URL=https://mycompany.atlassian.net/wiki" >> .env
echo "CONFLUENCE_USER=john@mycompany.com" >> .env
echo "CONFLUENCE_TOKEN=YOUR_API_TOKEN_HERE" >> .env

# Генерация из Confluence с кастомными опциями
./generate_tests.py \
  --source confluence:987654321 \
  --output confluence_tests \
  --format excel \
  --no-backup

# Просмотр загруженных требований
python main.py state show
```

---

### Формат требований

Можно использовать обычный текст или структурированный формат:

```markdown
# Обычный текст
API должен возвращать список питомцев с пагинацией. Параметры: limit (10-100), offset (0+).

# Структурированный (опционально)
[API] [Back]
## Получение списка питомцев
API должен возвращать список питомцев с пагинацией. Параметры: limit (10-100), offset (0+).

---

[UI] [Front]  
## Форма регистрации
Форма должна содержать поля email и пароль (8+ символов).
```

## Что дальше?

После генерации:

1. **Проверьте результаты**: `artifacts/test_cases.xlsx`
2. **Просмотрите state**: `python main.py state show`
3. **При необходимости повторите**: команда идемпотентна

## Альтернативный способ (step-by-step)

Если нужно использовать пошаговый подход:

```bash
# 1. Загрузка
python main.py load-raw --dir requirements/raw

# 2. Просмотр
python main.py state show

# 3. Экспорт (без генерации, если уже есть тесты в state)
python main.py state export -f excel -o artifacts/test_cases
```

Но проще использовать **`./generate_tests.py`** - он делает всё автоматически.

## Помощь

```bash
# Список всех команд
python main.py --help

# Справка по команде generate
./generate_tests.py --help

# Доступные техники тест-дизайна
python main.py techniques
```
