"""
Генератор тест-кейсов - загрузка требований и экспорт результатов.

В режиме CLI агента тесты генерируются самим агентом, а этот модуль
отвечает за загрузку требований и экспорт результатов.
"""
from pathlib import Path
from typing import Optional

from src.parsers.confluence_parser import ConfluenceParser
from src.agents.test_agent import GenerationResult
from src.generators.exporters import ExcelExporter, CSVExporter, AllureCSVExporter
from src.state.state_manager import StateManager
from src.utils.logger import setup_logger
from src.utils.input_validation import validate_file_size, validate_file_path, validate_requirement_length

logger = setup_logger(__name__)


class TestCaseGenerator:
    """
    Загрузчик требований и экспортер результатов.

    В режиме CLI агента:
    - load_* методы загружают требования в state
    - export_* методы экспортируют результаты из state
    - Генерацией занимается сам CLI агент
    """

    def __init__(
        self,
        confluence_parser: Optional[ConfluenceParser] = None,
        state_manager: Optional[StateManager] = None
    ):
        """
        Инициализация генератора.

        Args:
            confluence_parser: Парсер Confluence (создается автоматически)
            state_manager: Менеджер состояния (создается автоматически)
        """
        self.confluence = confluence_parser
        self.state = state_manager or StateManager()
        logger.info("TestCaseGenerator инициализирован")

    def _ensure_confluence(self) -> ConfluenceParser:
        """Ленивая инициализация Confluence парсера."""
        if self.confluence is None:
            self.confluence = ConfluenceParser()
        return self.confluence

    def load_from_confluence(self, page_id: str) -> list[str]:
        """
        Загружает требования из Confluence в state.

        Args:
            page_id: ID страницы в Confluence

        Returns:
            Список загруженных требований
        """
        logger.info(f"Загрузка страницы Confluence: {page_id}")

        confluence = self._ensure_confluence()
        page = confluence.get_page_content(page_id)

        logger.info(f"Страница загружена: {page['title']}")

        requirements = confluence.extract_requirements(page["content"])
        logger.info(f"Извлечено {len(requirements)} требований")

        if not requirements:
            logger.warning("Требования не найдены на странице")
            return []

        # Добавляем в state
        self.state.get_or_create_session()
        for req_text in requirements:
            is_valid, error = validate_requirement_length(req_text)
            if not is_valid:
                logger.warning(f"Требование пропущено: {error}")
                continue
            self.state.add_requirement(
                text=req_text,
                source="confluence",
                source_ref=page_id
            )

        return requirements

    def load_from_file(self, file_path: str) -> list[str]:
        """
        Загружает требования из файла в state.

        Args:
            file_path: Путь к файлу

        Returns:
            Список загруженных требований
        """
        is_valid, error = validate_file_path(file_path, allow_absolute=True)
        if not is_valid:
            raise ValueError(f"Invalid file path: {error}")

        path = Path(file_path)
        is_valid, error = validate_file_size(path)
        if not is_valid:
            raise ValueError(f"Invalid file: {error}")

        logger.info(f"Чтение требований из файла: {path}")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Разделяем файл на отдельные требования
        requirements = self._split_requirements(content)
        logger.info(f"Найдено {len(requirements)} требований в файле")

        # Добавляем в state
        self.state.get_or_create_session()
        for req_text in requirements:
            is_valid, error = validate_requirement_length(req_text)
            if not is_valid:
                logger.warning(f"Требование пропущено: {error}")
                continue
            self.state.add_requirement(
                text=req_text,
                source="file",
                source_ref=str(path)
            )

        return requirements

    def load_from_text(self, text: str) -> str:
        """
        Загружает одно требование из текста в state.

        Args:
            text: Текст требования

        Returns:
            Текст требования
        """
        logger.info("Загрузка требования из текста")

        is_valid, error = validate_requirement_length(text)
        if not is_valid:
            raise ValueError(f"Invalid requirement: {error}")

        self.state.get_or_create_session()
        self.state.add_requirement(text=text, source="manual")

        return text

    def _split_requirements(self, content: str) -> list[str]:
        """Разделяет текст на отдельные требования."""
        separators = ["\n\n---\n\n", "\n---\n", "\n\n"]

        requirements = [content]
        for sep in separators:
            new_reqs = []
            for req in requirements:
                new_reqs.extend(req.split(sep))
            requirements = new_reqs

        # Фильтруем пустые и слишком короткие
        return [r.strip() for r in requirements if len(r.strip()) >= 50]

    def export_to_excel(
        self,
        results: list[GenerationResult],
        output_path: str,
        include_analysis: bool = True,
        group_by_layer: bool = False
    ) -> str:
        """
        Экспортирует результаты в Excel.

        Args:
            results: Результаты генерации
            output_path: Путь для сохранения файла
            include_analysis: Включить лист с анализом требований
            group_by_layer: Группировать тест-кейсы по слоям (api, ui, integration, e2e)

        Returns:
            Путь к созданному файлу
        """
        exporter = ExcelExporter()
        return exporter.export(results, output_path, include_analysis, group_by_layer)

    def export_to_csv(
        self,
        results: list[GenerationResult],
        output_path: str
    ) -> str:
        """
        Экспортирует результаты в CSV.

        Args:
            results: Результаты генерации
            output_path: Путь для сохранения файла

        Returns:
            Путь к созданному файлу
        """
        exporter = CSVExporter()
        return exporter.export(results, output_path)

    def export_to_allure_csv(
        self,
        results: list[GenerationResult],
        output_path: str,
        status: str = "Draft",
        suite: str = "",
        feature: str = "",
        epic: str = "",
        owner: str = "",
        jira_link: str = ""
    ) -> str:
        """
        Экспортирует результаты в CSV для Allure TestOps.

        Формат соответствует реальному экспорту Allure TestOps:
        - Разделитель: точка с запятой (;)
        - Сценарий: [step N] для шагов, [expected N.1] для результатов
        - Поддержка Suite, Feature, Epic, Owner, Jira

        Args:
            results: Результаты генерации
            output_path: Путь для сохранения файла
            status: Статус тест-кейсов (Draft, Ready, etc.)
            suite: Название Suite для всех тест-кейсов
            feature: Название Feature
            epic: Название Epic
            owner: Владелец тест-кейсов
            jira_link: Ссылка на задачу в Jira

        Returns:
            Путь к созданному файлу
        """
        exporter = AllureCSVExporter()
        return exporter.export(
            results, output_path, status, suite, feature, epic, owner, jira_link
        )

    def get_pending_requirements(self) -> list[str]:
        """Возвращает список необработанных требований."""
        pending = self.state.get_pending_requirements()
        return [req.text for req in pending]

    def get_state_summary(self) -> dict:
        """Возвращает сводку по текущему состоянию."""
        return self.state.get_summary()
