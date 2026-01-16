#!/usr/bin/env python3
"""
Metrics Dashboard для AI Test Generator
HTML-визуализация метрик в стиле Jony Ive (Apple Design)
"""

import json
import logging
import csv
from pathlib import Path
from datetime import datetime
from collections import Counter
import sys

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def load_test_cases(csv_path: str = None, state_path: str = None) -> list:
    """Загрузка тест-кейсов из CSV или state файла"""
    logger.info("Начало загрузки тест-кейсов")

    if csv_path and Path(csv_path).exists():
        logger.debug(f"Загрузка из CSV: {csv_path}")
        test_cases = []
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    test_cases.append(row)
            logger.info(f"Загружено {len(test_cases)} тест-кейсов из CSV")
            return test_cases
        except Exception as e:
            logger.error(f"Ошибка чтения CSV: {e}")
            raise

    if state_path and Path(state_path).exists():
        logger.debug(f"Загрузка из state: {state_path}")
        try:
            with open(state_path, 'r', encoding='utf-8') as f:
                state = json.load(f)

            test_cases = []
            for req in state.get('requirements', []):
                for tc in req.get('test_cases', []):
                    tc['requirement_id'] = req['id']
                    tc['Requirement'] = req.get('text', '')[:100]
                    test_cases.append(tc)
            logger.info(f"Загружено {len(test_cases)} тест-кейсов из state")
            return test_cases
        except Exception as e:
            logger.error(f"Ошибка чтения state: {e}")
            raise

    logger.error("Файл с тест-кейсами не найден")
    raise FileNotFoundError("No test cases file found")


def extract_requirement_id(req_text: str) -> str:
    """Извлечь ID требования из текста"""
    if not req_text:
        return "Unknown"
    if req_text.startswith("## REQ-"):
        return req_text.split(":")[0].replace("## ", "")
    if req_text.startswith("REQ-"):
        return req_text.split(":")[0]
    return req_text[:20] + "..."


def calculate_metrics(test_cases: list) -> dict:
    """Расчёт всех метрик"""
    logger.info("Расчёт метрик")

    total = len(test_cases)
    logger.debug(f"Всего тест-кейсов: {total}")

    # Маппинг для русификации
    priority_ru = {'Critical': 'Критический', 'High': 'Высокий', 'Medium': 'Средний', 'Low': 'Низкий'}
    type_ru = {'Positive': 'Позитивные', 'Negative': 'Негативные', 'Boundary': 'Граничные', 'Edge': 'Крайние'}
    technique_ru = {
        'EP: Invalid Class': 'ЭК: Невалидный класс',
        'EP: Valid Class': 'ЭК: Валидный класс',
        'Use Case Testing: Happy Path': 'Use Case: Позитивный сценарий',
        'State Transition: Valid Path': 'Переходы состояний: Валидный путь',
        'State Transition: Invalid Path': 'Переходы состояний: Невалидный путь',
        'EP: Non-existent Resource': 'ЭК: Несуществующий ресурс',
        'Error Guessing: Duplicate ID': 'Угадывание ошибок: Дубликат ID',
        'EP: Missing Required Fields': 'ЭК: Отсутствуют обязательные поля',
        'Error Guessing: Invalid ID Format': 'Угадывание ошибок: Неверный формат ID',
        'EP: Empty Result Set': 'ЭК: Пустой результат',
    }

    priorities = Counter()
    types = Counter()
    techniques = Counter()
    requirements = Counter()

    for tc in test_cases:
        priority = tc.get('Priority') or tc.get('priority', 'Unknown')
        priorities[priority_ru.get(priority, priority)] += 1

        test_type = tc.get('Test Type') or tc.get('test_type', 'Unknown')
        types[type_ru.get(test_type, test_type)] += 1

        technique = tc.get('Technique') or tc.get('technique', 'Unknown')
        techniques[technique_ru.get(technique, technique)] += 1

        req = tc.get('Requirement') or tc.get('requirement_id', 'Unknown')
        req_id = extract_requirement_id(req)
        requirements[req_id] += 1

    metrics = {
        'total': total,
        'priorities': dict(priorities.most_common()),
        'types': dict(types.most_common()),
        'techniques': dict(techniques.most_common(10)),
        'requirements': dict(requirements.most_common()),
        'generated_at': datetime.now().strftime("%d.%m.%Y %H:%M"),
    }

    logger.info(f"Метрики рассчитаны: {len(metrics['requirements'])} требований, {len(metrics['techniques'])} техник")
    return metrics


def generate_html_dashboard(metrics: dict) -> str:
    """Генерация HTML дашборда в стиле Jony Ive"""
    logger.info("Генерация HTML дашборда")

    priorities_data = metrics['priorities']
    types_data = metrics['types']
    techniques_data = metrics['techniques']
    requirements_data = metrics['requirements']

    # Подсчёт процентов для приоритетов
    total = metrics['total']
    priority_items = []
    priority_colors = {
        'Критический': '#FF3B30',
        'Высокий': '#FF9500',
        'Средний': '#34C759',
        'Низкий': '#007AFF',
    }

    for name, count in priorities_data.items():
        pct = round(count / total * 100, 1)
        color = priority_colors.get(name, '#8E8E93')
        priority_items.append({'name': name, 'count': count, 'pct': pct, 'color': color})

    # Подсчёт для типов
    type_colors = {'Позитивные': '#34C759', 'Негативные': '#FF3B30', 'Граничные': '#FF9500'}
    type_items = []
    for name, count in types_data.items():
        pct = round(count / total * 100, 1)
        color = type_colors.get(name, '#8E8E93')
        type_items.append({'name': name, 'count': count, 'pct': pct, 'color': color})

    logger.debug("Формирование HTML структуры")

    html = f'''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Метрики тестирования</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #F5F5F7;
            color: #1D1D1F;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 60px 40px;
        }}

        /* Header */
        header {{
            text-align: center;
            margin-bottom: 60px;
        }}

        header h1 {{
            font-size: 48px;
            font-weight: 600;
            letter-spacing: -0.5px;
            color: #1D1D1F;
            margin-bottom: 12px;
        }}

        header p {{
            font-size: 17px;
            color: #86868B;
            font-weight: 400;
        }}

        /* Stats Row */
        .stats-row {{
            display: flex;
            justify-content: center;
            gap: 60px;
            margin-bottom: 80px;
        }}

        .stat-item {{
            text-align: center;
        }}

        .stat-number {{
            font-size: 64px;
            font-weight: 600;
            color: #1D1D1F;
            letter-spacing: -2px;
            line-height: 1;
        }}

        .stat-label {{
            font-size: 14px;
            color: #86868B;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 8px;
        }}

        /* Cards Grid */
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
            margin-bottom: 24px;
        }}

        .card {{
            background: #FFFFFF;
            border-radius: 18px;
            padding: 32px;
            box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
        }}

        .card-title {{
            font-size: 13px;
            font-weight: 500;
            color: #86868B;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 24px;
        }}

        /* Priority List */
        .metric-list {{
            display: flex;
            flex-direction: column;
            gap: 16px;
        }}

        .metric-row {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}

        .metric-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            flex-shrink: 0;
        }}

        .metric-name {{
            flex: 1;
            font-size: 15px;
            color: #1D1D1F;
        }}

        .metric-value {{
            font-size: 15px;
            font-weight: 500;
            color: #1D1D1F;
            min-width: 40px;
            text-align: right;
        }}

        .metric-pct {{
            font-size: 13px;
            color: #86868B;
            min-width: 50px;
            text-align: right;
        }}

        /* Progress Bars */
        .progress-list {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}

        .progress-item {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .progress-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .progress-name {{
            font-size: 14px;
            color: #1D1D1F;
        }}

        .progress-value {{
            font-size: 14px;
            color: #86868B;
        }}

        .progress-bar {{
            height: 6px;
            background: #E5E5EA;
            border-radius: 3px;
            overflow: hidden;
        }}

        .progress-fill {{
            height: 100%;
            border-radius: 3px;
            transition: width 0.6s ease;
        }}

        /* Requirements */
        .req-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }}

        .req-chip {{
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 16px;
            background: #F5F5F7;
            border-radius: 20px;
        }}

        .req-chip-name {{
            font-size: 14px;
            font-weight: 500;
            color: #1D1D1F;
        }}

        .req-chip-count {{
            font-size: 13px;
            color: #86868B;
        }}

        /* Techniques Table */
        .techniques-table {{
            width: 100%;
        }}

        .tech-row {{
            display: flex;
            align-items: center;
            padding: 14px 0;
            border-bottom: 1px solid #F5F5F7;
        }}

        .tech-row:last-child {{
            border-bottom: none;
        }}

        .tech-name {{
            flex: 1;
            font-size: 14px;
            color: #1D1D1F;
        }}

        .tech-bar {{
            width: 120px;
            height: 4px;
            background: #E5E5EA;
            border-radius: 2px;
            margin: 0 16px;
            overflow: hidden;
        }}

        .tech-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #007AFF, #5856D6);
            border-radius: 2px;
        }}

        .tech-count {{
            font-size: 14px;
            font-weight: 500;
            color: #1D1D1F;
            min-width: 32px;
            text-align: right;
        }}

        /* Footer */
        footer {{
            text-align: center;
            padding: 40px 0;
            color: #86868B;
            font-size: 13px;
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 40px 20px;
            }}

            header h1 {{
                font-size: 32px;
            }}

            .stats-row {{
                flex-wrap: wrap;
                gap: 40px;
            }}

            .stat-number {{
                font-size: 48px;
            }}

            .cards-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Метрики тестирования</h1>
            <p>Сгенерировано {metrics['generated_at']}</p>
        </header>

        <div class="stats-row">
            <div class="stat-item">
                <div class="stat-number">{metrics['total']}</div>
                <div class="stat-label">Тест-кейсов</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{len(metrics['requirements'])}</div>
                <div class="stat-label">Требований</div>
            </div>
            <div class="stat-item">
                <div class="stat-number">{len(metrics['techniques'])}</div>
                <div class="stat-label">Техник</div>
            </div>
        </div>

        <div class="cards-grid">
            <div class="card">
                <div class="card-title">Приоритет</div>
                <div class="metric-list">
                    {generate_priority_rows(priority_items)}
                </div>
            </div>

            <div class="card">
                <div class="card-title">Тип тестирования</div>
                <div class="progress-list">
                    {generate_type_bars(type_items)}
                </div>
            </div>
        </div>

        <div class="cards-grid">
            <div class="card">
                <div class="card-title">Покрытие требований</div>
                <div class="req-grid">
                    {generate_requirements_chips(requirements_data)}
                </div>
            </div>

            <div class="card">
                <div class="card-title">Техники тестирования</div>
                <div class="techniques-table">
                    {generate_techniques_rows(techniques_data)}
                </div>
            </div>
        </div>

        <footer>
            AI Test Generator v1.0
        </footer>
    </div>
</body>
</html>'''

    logger.info("HTML дашборд сгенерирован")
    return html


def generate_priority_rows(items: list) -> str:
    """Генерация строк приоритетов"""
    rows = []
    for item in items:
        rows.append(f'''
            <div class="metric-row">
                <div class="metric-dot" style="background: {item['color']}"></div>
                <div class="metric-name">{item['name']}</div>
                <div class="metric-value">{item['count']}</div>
                <div class="metric-pct">{item['pct']}%</div>
            </div>
        ''')
    return '\n'.join(rows)


def generate_type_bars(items: list) -> str:
    """Генерация прогресс-баров для типов"""
    rows = []
    max_pct = max(item['pct'] for item in items) if items else 100

    for item in items:
        bar_width = item['pct'] / max_pct * 100
        rows.append(f'''
            <div class="progress-item">
                <div class="progress-header">
                    <span class="progress-name">{item['name']}</span>
                    <span class="progress-value">{item['count']} ({item['pct']}%)</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {bar_width}%; background: {item['color']}"></div>
                </div>
            </div>
        ''')
    return '\n'.join(rows)


def generate_requirements_chips(requirements: dict) -> str:
    """Генерация чипов для требований"""
    chips = []
    for name, count in requirements.items():
        chips.append(f'''
            <div class="req-chip">
                <span class="req-chip-name">{name}</span>
                <span class="req-chip-count">{count}</span>
            </div>
        ''')
    return '\n'.join(chips)


def generate_techniques_rows(techniques: dict) -> str:
    """Генерация строк техник"""
    rows = []
    max_count = max(techniques.values()) if techniques else 1

    for technique, count in techniques.items():
        bar_width = count / max_count * 100
        display_name = technique if len(technique) <= 35 else technique[:32] + '...'

        rows.append(f'''
            <div class="tech-row">
                <div class="tech-name" title="{technique}">{display_name}</div>
                <div class="tech-bar">
                    <div class="tech-bar-fill" style="width: {bar_width}%"></div>
                </div>
                <div class="tech-count">{count}</div>
            </div>
        ''')
    return '\n'.join(rows)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Генерация HTML дашборда метрик')
    parser.add_argument('-i', '--input', default='artifacts/test_cases.csv',
                       help='Путь к CSV файлу с тест-кейсами')
    parser.add_argument('-s', '--state', default='.test_generator_state.json',
                       help='Путь к JSON файлу состояния')
    parser.add_argument('-o', '--output', default='artifacts/metrics_dashboard.html',
                       help='Путь для сохранения HTML дашборда')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Подробный вывод логов')

    args = parser.parse_args()

    # Настройка уровня логирования
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Включен подробный режим логирования")

    logger.info("Запуск генератора дашборда метрик")

    # Определить рабочую директорию
    project_root = Path(__file__).parent.parent
    logger.debug(f"Корневая директория проекта: {project_root}")

    csv_path = project_root / args.input
    state_path = project_root / args.state
    output_path = project_root / args.output

    # Загрузить данные
    try:
        if csv_path.exists():
            logger.info(f"Найден CSV файл: {csv_path}")
            test_cases = load_test_cases(csv_path=str(csv_path))
        elif state_path.exists():
            logger.info(f"Найден state файл: {state_path}")
            test_cases = load_test_cases(state_path=str(state_path))
        else:
            logger.error(f"Файлы не найдены: {csv_path}, {state_path}")
            sys.exit(1)
    except Exception as e:
        logger.exception(f"Критическая ошибка загрузки данных: {e}")
        sys.exit(1)

    # Расчёт метрик
    try:
        metrics = calculate_metrics(test_cases)
    except Exception as e:
        logger.exception(f"Ошибка расчёта метрик: {e}")
        sys.exit(1)

    # Генерация HTML
    try:
        html = generate_html_dashboard(metrics)
    except Exception as e:
        logger.exception(f"Ошибка генерации HTML: {e}")
        sys.exit(1)

    # Сохранение
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"Дашборд сохранён: {output_path}")
    except Exception as e:
        logger.exception(f"Ошибка сохранения файла: {e}")
        sys.exit(1)

    # Итоговый отчёт
    logger.info("=" * 50)
    logger.info("ОТЧЁТ ПО МЕТРИКАМ")
    logger.info("=" * 50)
    logger.info(f"Всего тест-кейсов: {metrics['total']}")
    logger.info(f"Требований: {len(metrics['requirements'])}")
    logger.info(f"Техник: {len(metrics['techniques'])}")
    for p, c in metrics['priorities'].items():
        logger.info(f"  {p}: {c} ({c/metrics['total']*100:.1f}%)")
    logger.info("=" * 50)

    print(f"\n✓ Дашборд сохранён: {output_path}")


if __name__ == '__main__':
    main()
