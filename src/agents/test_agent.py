"""
Модели данных и хелперы для генерации тест-кейсов.

В режиме CLI агента (Claude Code, Qwen Code и др.) сам агент выступает
в роли LLM и генерирует тесты напрямую, используя промпты из проекта.
"""
import json
from dataclasses import dataclass, field

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class TestCase:
    """Модель тест-кейса."""
    id: str
    title: str
    priority: str  # Critical, High, Medium, Low
    preconditions: list[str]
    steps: list[dict]  # [{"step": 1, "action": "..."}]
    expected_result: str
    test_type: str  # Positive, Negative, Boundary, Edge
    technique: str  # Test design technique used

    # Новые поля для расширенной классификации (с defaults для обратной совместимости)
    layer: str = "api"  # api | ui | integration | e2e
    component: str = "fullstack"  # backend | frontend | fullstack
    tags: list[str] = field(default_factory=list)
    ui_element: str | None = None  # Для UI тестов: название элемента
    api_endpoint: str | None = None  # Для API тестов: эндпоинт


@dataclass
class RequirementAnalysis:
    """Анализ требования."""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)


@dataclass
class GenerationResult:
    """Результат генерации тестов."""
    requirement_text: str
    analysis: RequirementAnalysis
    test_cases: list[TestCase]
    tokens_used: int = 0
    model: str = "cli_agent"


# Доступные техники тест-дизайна
AVAILABLE_TECHNIQUES = [
    "equivalence_partitioning",
    "boundary_value",
    "decision_table",
    "state_transition",
    "use_case",
    "pairwise",
    "error_guessing",
    # UI техники
    "ui_calendar",
    "ui_form",
    "ui_file_upload",
    # LLM и интеграции
    "llm_integration",
    "backend_frontend_integration",
]


def parse_test_cases_json(json_str: str) -> tuple[RequirementAnalysis, list[TestCase]]:
    """
    Парсит JSON с тест-кейсами в структурированный формат.

    Используется CLI агентом для преобразования своего вывода
    в объекты проекта.

    Args:
        json_str: JSON строка с результатом генерации

    Returns:
        Кортеж (RequirementAnalysis, list[TestCase])
    """
    # Извлекаем JSON из markdown блока если есть
    content = json_str
    if "```json" in content:
        start = content.find("```json") + 7
        end = content.find("```", start)
        if end > start:
            content = content[start:end].strip()
    elif "```" in content:
        start = content.find("```") + 3
        end = content.find("```", start)
        if end > start:
            potential = content[start:end].strip()
            if potential.startswith("{"):
                content = potential

    # Ищем JSON напрямую
    if not content.startswith("{"):
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            content = content[start:end]

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON: {e}")
        return RequirementAnalysis(), []

    # Парсим анализ требования
    analysis_data = data.get("requirement_analysis", {})
    analysis = RequirementAnalysis(
        inputs=analysis_data.get("inputs", []),
        outputs=analysis_data.get("outputs", []),
        business_rules=analysis_data.get("business_rules", []),
        states=analysis_data.get("states", [])
    )

    # Парсим тест-кейсы
    test_cases = []
    for tc_data in data.get("test_cases", []):
        tc = TestCase(
            id=tc_data.get("id", ""),
            title=tc_data.get("title", ""),
            priority=tc_data.get("priority", "Medium"),
            preconditions=tc_data.get("preconditions", []),
            steps=tc_data.get("steps", []),
            expected_result=tc_data.get("expected_result", ""),
            test_type=tc_data.get("test_type", ""),
            technique=tc_data.get("technique", ""),
            layer=tc_data.get("layer", "api"),
            component=tc_data.get("component", "fullstack"),
            tags=tc_data.get("tags", []),
            ui_element=tc_data.get("ui_element"),
            api_endpoint=tc_data.get("api_endpoint")
        )
        test_cases.append(tc)

    logger.info(f"Распарсено {len(test_cases)} тест-кейсов")
    return analysis, test_cases


def format_test_case_console(tc: TestCase) -> str:
    """
    Форматирует тест-кейс для вывода в консоль.

    Args:
        tc: Тест-кейс для форматирования

    Returns:
        Строка с отформатированным тест-кейсом
    """
    lines = [
        "━" * 50,
        f"{tc.id}: {tc.title}",
        "━" * 50,
        "",
        f"Приоритет: {tc.priority}",
        f"Тип: {tc.test_type}",
        f"Техника: {tc.technique}",
        f"Слой: {tc.layer}",
        f"Компонент: {tc.component}",
    ]

    if tc.tags:
        lines.append(f"Теги: {', '.join(tc.tags)}")
    if tc.ui_element:
        lines.append(f"UI элемент: {tc.ui_element}")
    if tc.api_endpoint:
        lines.append(f"API endpoint: {tc.api_endpoint}")

    lines.extend([
        "",
        "Предусловия:"
    ])

    for pre in tc.preconditions:
        lines.append(f"  • {pre}")

    lines.append("")
    lines.append("Шаги:")

    for step in tc.steps:
        lines.append(f"  {step['step']}. {step['action']}")

    lines.append("")
    lines.append("Ожидаемый результат:")
    lines.append(f"  {tc.expected_result}")
    lines.append("")

    return "\n".join(lines)


def format_test_cases_batch(test_cases: list[TestCase]) -> str:
    """Форматирует список тест-кейсов для консоли."""
    return "\n".join(format_test_case_console(tc) for tc in test_cases)
