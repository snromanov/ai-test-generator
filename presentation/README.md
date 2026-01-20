# AI Test Generator - Executive Presentation

Продающая презентация для руководства банка о внедрении AI Test Generator.

## Структура

```
presentation/
├── generate_presentation.py   # Скрипт генерации PPTX
├── data/
│   ├── downtime_costs.json    # Данные о стоимости простоев (реальные источники)
│   └── roi_calculations.json  # ROI расчёты
├── charts/                    # Автоматически генерируемые графики
│   ├── time_comparison.png
│   ├── roi_comparison.png
│   ├── downtime_cost_growth.png
│   └── risk_timeline.png
└── output/
    └── ai_test_generator_pitch.pptx  # Финальная презентация
```

## Использование

### Генерация презентации

```bash
# Из корня проекта
python presentation/generate_presentation.py

# Или с указанием venv
./venv/bin/python presentation/generate_presentation.py
```

### Открытие презентации

Файл `presentation/output/ai_test_generator_pitch.pptx` можно открыть в:
- Microsoft PowerPoint
- Google Slides (импорт)
- LibreOffice Impress
- Keynote (macOS)

## Содержание презентации (12 слайдов)

| # | Слайд | Описание |
|---|-------|----------|
| 1 | Title | Заголовок + ключевое сообщение |
| 2 | Problem | Критический риск - 0% покрытия инфраструктуры |
| 3 | Cost of Downtime | Стоимость простоев (Gartner, Uptime Institute) |
| 4 | Real Incidents | Knight Capital, TSB Bank, RBS - реальные кейсы |
| 5 | Traditional Solutions | Почему найм/перераспределение не работают |
| 6 | Our Solution | AI Test Generator - как это работает |
| 7 | Demo Results | PetStore API: 52 тест-кейса за 5 минут |
| 8 | Pilot Proposal | 4-недельный пилот для Infrastructure |
| 9 | ROI | 14.6M экономии за 3 года, ROI 1,200% |
| 10 | Risk Timeline | Путь от CRITICAL к CONTROLLED |
| 11 | Call to Action | Одобрить пилот vs альтернатива |
| 12 | Contact | Вопросы и контакты |

## Источники данных

### Стоимость простоев
- **Gartner Research 2024**: $5,600/мин средний, $5M+/час финансовый сектор
- **Uptime Institute Annual Outage Analysis 2024**: 54% простоев стоят >$100k, 20% >$1M
- **ITIC 2024 Survey**: 90% компаний теряют >$300k/час
- **Splunk/Oxford Economics**: $152M годовые потери в финансовом секторе

### Реальные инциденты
- **Knight Capital (2012)**: $440M за 45 минут из-за бага в деплое
- **TSB Bank (2018)**: £330M потерь, £49M штрафов из-за провала миграции
- **RBS/NatWest (2012)**: £231M потерь, 6.5M клиентов пострадали

## Кастомизация

### Изменение данных

Отредактируйте JSON файлы в `data/`:
- `downtime_costs.json` - данные о стоимости простоев
- `roi_calculations.json` - ROI расчёты и параметры пилота

### Изменение дизайна

В `generate_presentation.py` можно изменить:
- `COLORS` - цветовую схему
- Размеры и позиции элементов (в Inches)
- Тексты и структуру слайдов

### Перегенерация

После изменений запустите скрипт заново:
```bash
python presentation/generate_presentation.py
```

## Требования

- Python 3.8+
- python-pptx
- matplotlib

Установка зависимостей:
```bash
pip install python-pptx matplotlib
```

## Советы по презентации

### Подготовка
1. Просмотрите speaker notes на каждом слайде
2. Подготовьте ответы на возможные вопросы
3. Имейте demo готовым (PetStore API пример)

### Ключевые сообщения
- **Риск реален**: Knight Capital потерял $440M за 45 минут
- **ROI убедителен**: 14.6M экономии за 3 года
- **Время критично**: каждый месяц без покрытия = накопление риска
- **Барьер низкий**: MVP готов, 0₽ budget на пилот

### Возможные вопросы
1. *"Насколько точны тест-кейсы?"* - 52 тест-кейса из 9 endpoints, включая edge cases
2. *"Безопасность данных?"* - On-premise, данные не покидают банк
3. *"Что если AI ошибётся?"* - Инженеры ревьюят и выполняют тесты
4. *"Почему Claude, а не GPT?"* - Лучше для structured output, 200k контекст

## Лицензия

Internal use only.
