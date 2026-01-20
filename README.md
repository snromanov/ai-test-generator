# AI Test Generator

**AI Test Generator** — CLI-first инструмент для работы с требованиями, состояния и экспорта тест-кейсов. Основной сценарий: один запуск генерирует тесты из raw/demo/Confluence и экспортирует в Excel/CSV.

## Диаграмма компонентов

![AI Test Generator UML (Component)](https://www.plantuml.com/plantuml/svg/NLNRRjim37ttLmXvQWV4_OEYXf6wHkt6jPrWm304cgEaQXNPbUGXsR1_7obBIjAt8_BmuaCoUT26AZCUH6Iu4OmaEMcPDYHZaYbgUaNcP5KMv2Rj3qClcJItqHlVCg8DKwmtfu7fA1fezq7tZCmMqgWJgNekZPwHln4XFmwKotWu_IHKaxJ8qRIVahEDWLBQExCMVINzO3ikc3MLpz6_Y-mL7vZWaldK_hrKtHjailtQk6fv7KULPif7DKQDdHaLszRiS-IA7U2h9eeDRkeAQMalTs9aicCNlhIwIXnKyhbHkvHg5XmsgaqpT2wEGwz0Dark5iUEYRkqMTzQmkBxTTvAWTf1mK-w6IQ3b-erGVl8lzfNLbuX3XiO0Dj31xoNNqb5KLuLQmoC8cW3kAGI74wC4inRQkWl-2eoYt5Ycxt_ker6VlokUpcpx3Pf5n200mGovNFapu4_rtmlAQe-_s2dYPndLtsi31UNEWODdvWON3jjzeJkYy4baehJ7-UkhIwfO5IEWzku5xifgdzddSdbhfyMn0gLos4qQohurWfbFVaQFKM_zmeKo-is6zQDYfkJwrIxfrUtMQJMhDKEXJTG5L87RrC_ejjkl-073klWVNLX0r5HDxxBjFbbiOs0_hZS1sznrMBPRrcGqauCpD9uTcBdFyq8Zf_lQ6VqtRVuAFJnBkxqRpkUvQgDEj6FMp8xdm99gjnwq-NBOmHny0CnWwic2HQmdYHRlBHHL3wJEBx7eyvQCf_VszkFa8eFE50FOSCyn3i9PhX2Zs6iWG8Bu37EDYJC0uG9UfYSSx-USwpENBo5g5g6T0v2JmvXFGUX2s-4FXt4o_L1TO3GWaEuFH7mfmfLW531GqpXCGHwE4LcJu7k8Dhh93Jd85gXWNDaEc6xS0x3WZbaf-SPmMhZcdAomXfxc7i4tNcRFVH0o08iFBB9uDFi0tV9OvY9XvRpclW1GisG1Dhsk2w2DVSeNuS4CBQ0gpp0vA8Dkv9s7M4BpW-Kxu79BVxx_GS0)

Источник диаграммы: `UML.puml`.

## Возможности

- Загрузка требований из raw-файлов, demo и Confluence
- Единый pipeline: загрузка → анализ → генерация → экспорт
- Экспорт в Excel/CSV, группировка по слоям (API/UI/Integration/E2E)
- Встроенные техники тест-дизайна (BVA/EP и др.)

## Установка

```bash
git clone <repository-url>
cd ai-test-generator
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

Альтернатива через Makefile:

```bash
make setup
```

## Быстрый старт

### 1) Demo

```bash
./generate_tests.py --source demo/petstore
```

### 2) Raw (по умолчанию)

```bash
./generate_tests.py
```

### 3) Confluence

```bash
./generate_tests.py --source confluence:PAGE_ID
```

Результаты: `artifacts/test_cases.xlsx` (и CSV при `--format both`).
Полное руководство: `QUICKSTART.md`.

### Быстрые команды Makefile

```bash
make gen
make gen-demo
make gen-confluence PAGE_ID=123456789
make export
make clean
```

## Конфигурация Confluence (опционально)

```bash
cp .env.example .env
```

```ini
CONFLUENCE_URL=https://your-company.atlassian.net/wiki
CONFLUENCE_USER=your-email@company.com
CONFLUENCE_TOKEN=your-confluence-api-token
LOG_LEVEL=INFO
```

## CLI команды (коротко)

```bash
# Полный pipeline (generate)
python main.py generate --source demo/petstore

# Состояние
python main.py state show
python main.py state export -f excel -o artifacts/test_cases

# Очистка
python main.py clean -y

# Загрузка требований
python main.py load-raw --dir requirements/raw
python main.py load-file requirements.md
python main.py load-demo --name petstore
python main.py load-confluence PAGE_ID
```

Дополнительно: `python main.py --help`.

## Структура проекта

```
ai-test-generator/
├── src/
│   ├── agents/          # Модели результатов
│   ├── generators/      # Генерация/экспорт
│   ├── parsers/         # Парсеры (Confluence, structured)
│   ├── pipelines/       # Orchestrator
│   ├── prompts/         # Промпты
│   ├── state/           # State Manager
│   └── utils/           # Утилиты
├── demo/
├── requirements/
│   └── raw/
├── artifacts/
├── main.py
├── generate_tests.py
├── Makefile
├── UML.puml
├── QUICKSTART.md
└── README.md
```

## Документация

| Документ | Описание |
|----------|----------|
| `QUICKSTART.md` | Быстрый старт и примеры |
| `WORKFLOW.md` | Пошаговый процесс |
| `AGENT.md` | Руководство для CLI агента |
| `ARCHITECTURE.md` | Архитектура |
| `SECURITY.md` | Безопасность |

## Требования

- Python 3.10+
- Зависимости из `requirements.txt`

## Лицензия

MIT
