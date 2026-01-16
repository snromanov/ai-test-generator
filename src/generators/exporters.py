"""
Экспортеры тест-кейсов в различные форматы с защитой от инъекций.
"""
import csv
from pathlib import Path
from typing import Protocol

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.agents.test_agent import GenerationResult, TestCase
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def sanitize_for_excel(text: str) -> str:
    """
    Защита от Formula Injection в Excel.
    
    Excel интерпретирует ячейки начинающиеся с =, +, -, @ как формулы.
    Это может привести к выполнению вредоносного кода.
    
    Args:
        text: Текст для санитизации
        
    Returns:
        Безопасный текст с префиксом ' если необходимо
    """
    if not text or not isinstance(text, str):
        return text
    
    # Опасные символы в начале ячейки
    dangerous_starts = ['=', '+', '-', '@', '\t', '\r', '\n']
    
    # Проверяем первый символ
    if text and text[0] in dangerous_starts:
        # Добавляем одинарную кавычку - Excel будет трактовать как текст
        logger.debug(f"Sanitized Excel formula injection attempt: {text[:50]}")
        return "'" + text
    
    return text


class Exporter(Protocol):
    """Протокол для экспортеров."""

    def export(self, results: list[GenerationResult], output_path: str) -> str:
        """Экспортирует результаты в файл."""
        ...


class ExcelExporter:
    """Экспортер в формат Excel (.xlsx)."""

    # Стили для Excel
    HEADER_FONT = Font(bold=True, color="FFFFFF")
    HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
    CELL_ALIGNMENT = Alignment(vertical="top", wrap_text=True)
    THIN_BORDER = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin")
    )

    PRIORITY_COLORS = {
        "Critical": "FF0000",
        "High": "FFA500",
        "Medium": "FFFF00",
        "Low": "90EE90"
    }

    def export(
        self,
        results: list[GenerationResult],
        output_path: str,
        include_analysis: bool = True
    ) -> str:
        """
        Экспортирует результаты в Excel файл.

        Args:
            results: Список результатов генерации
            output_path: Путь для сохранения
            include_analysis: Включить лист с анализом

        Returns:
            Путь к созданному файлу
        """
        logger.info(f"Начало экспорта в Excel: {output_path}")
        wb = Workbook()

        # Создаем лист с тест-кейсами
        ws_tests = wb.active
        ws_tests.title = "Test Cases"
        self._create_test_cases_sheet(ws_tests, results)

        # Создаем лист с анализом если требуется
        if include_analysis:
            ws_analysis = wb.create_sheet("Requirements Analysis")
            self._create_analysis_sheet(ws_analysis, results)

        # Создаем сводный лист
        ws_summary = wb.create_sheet("Summary", 0)
        self._create_summary_sheet(ws_summary, results)

        # Сохраняем файл
        path = Path(output_path)
        if not path.suffix:
            path = path.with_suffix(".xlsx")

        wb.save(path)
        logger.info(f"Excel файл сохранен: {path}")
        return str(path)

    def _create_test_cases_sheet(self, ws, results: list[GenerationResult]):
        """Создает лист с тест-кейсами."""
        headers = [
            "ID", "Название", "Приоритет", "Предусловия",
            "Шаги", "Ожидаемый результат", "Тип теста", "Техника", "Требование"
        ]

        # Заголовки
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = self.HEADER_ALIGNMENT
            cell.border = self.THIN_BORDER

        # Данные
        row = 2
        for result in results:
            req_text = result.requirement_text[:100] + "..." if len(result.requirement_text) > 100 else result.requirement_text

            for tc in result.test_cases:
                self._write_test_case_row(ws, row, tc, req_text)
                row += 1

        # Настраиваем ширину колонок
        column_widths = [10, 40, 12, 30, 50, 40, 15, 25, 50]
        for i, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = width

        # Автофильтр
        ws.auto_filter.ref = ws.dimensions

    def _write_test_case_row(self, ws, row: int, tc: TestCase, req_text: str):
        """Записывает строку тест-кейса."""
        # Форматируем предусловия
        preconditions = "\n".join(f"- {p}" for p in tc.preconditions) if tc.preconditions else ""

        # Форматируем шаги
        steps = "\n".join(f"{s['step']}. {s['action']}" for s in tc.steps) if tc.steps else ""

        # Санитизируем все значения для защиты от formula injection
        values = [
            sanitize_for_excel(tc.id),
            sanitize_for_excel(tc.title),
            sanitize_for_excel(tc.priority),
            sanitize_for_excel(preconditions),
            sanitize_for_excel(steps),
            sanitize_for_excel(tc.expected_result),
            sanitize_for_excel(tc.test_type),
            sanitize_for_excel(tc.technique),
            sanitize_for_excel(req_text)
        ]

        for col, value in enumerate(values, 1):
            cell = ws.cell(row=row, column=col, value=value)
            cell.alignment = self.CELL_ALIGNMENT
            cell.border = self.THIN_BORDER

            # Подсветка приоритета
            if col == 3 and value in self.PRIORITY_COLORS:
                cell.fill = PatternFill(
                    start_color=self.PRIORITY_COLORS[value],
                    end_color=self.PRIORITY_COLORS[value],
                    fill_type="solid"
                )

    def _create_analysis_sheet(self, ws, results: list[GenerationResult]):
        """Создает лист с анализом требований."""
        headers = ["Требование", "Входные данные", "Выходные данные", "Бизнес-правила", "Состояния"]

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = self.HEADER_ALIGNMENT
            cell.border = self.THIN_BORDER

        row = 2
        for result in results:
            analysis = result.analysis
            values = [
                result.requirement_text[:200] + "..." if len(result.requirement_text) > 200 else result.requirement_text,
                "\n".join(f"- {i}" for i in analysis.inputs),
                "\n".join(f"- {o}" for o in analysis.outputs),
                "\n".join(f"- {r}" for r in analysis.business_rules),
                "\n".join(f"- {s}" for s in analysis.states) if analysis.states else "N/A"
            ]

            for col, value in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=value)
                cell.alignment = self.CELL_ALIGNMENT
                cell.border = self.THIN_BORDER

            row += 1

        # Ширина колонок
        column_widths = [60, 40, 40, 50, 30]
        for i, width in enumerate(column_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = width

    def _create_summary_sheet(self, ws, results: list[GenerationResult]):
        """Создает сводный лист."""
        # Заголовок
        ws.cell(row=1, column=1, value="Сводка по генерации тест-кейсов").font = Font(bold=True, size=14)

        # Статистика
        total_tests = sum(len(r.test_cases) for r in results)
        total_requirements = len(results)
        total_tokens = sum(r.tokens_used for r in results)

        stats = [
            ("Всего требований:", total_requirements),
            ("Всего тест-кейсов:", total_tests),
            ("Токенов использовано:", total_tokens),
        ]

        row = 3
        for label, value in stats:
            ws.cell(row=row, column=1, value=label).font = Font(bold=True)
            ws.cell(row=row, column=2, value=value)
            row += 1

        # Распределение по приоритетам
        row += 1
        ws.cell(row=row, column=1, value="Распределение по приоритетам:").font = Font(bold=True)
        row += 1

        priority_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for result in results:
            for tc in result.test_cases:
                if tc.priority in priority_counts:
                    priority_counts[tc.priority] += 1

        for priority, count in priority_counts.items():
            ws.cell(row=row, column=1, value=priority)
            ws.cell(row=row, column=2, value=count)
            row += 1

        # Распределение по техникам
        row += 1
        ws.cell(row=row, column=1, value="Распределение по техникам:").font = Font(bold=True)
        row += 1

        technique_counts = {}
        for result in results:
            for tc in result.test_cases:
                technique_counts[tc.technique] = technique_counts.get(tc.technique, 0) + 1

        for technique, count in sorted(technique_counts.items()):
            ws.cell(row=row, column=1, value=technique)
            ws.cell(row=row, column=2, value=count)
            row += 1

        ws.column_dimensions["A"].width = 35
        ws.column_dimensions["B"].width = 15


class CSVExporter:
    """Экспортер в формат CSV."""

    def export(self, results: list[GenerationResult], output_path: str) -> str:
        """
        Экспортирует результаты в CSV файл.

        Args:
            results: Список результатов генерации
            output_path: Путь для сохранения

        Returns:
            Путь к созданному файлу
        """
        logger.info(f"Начало экспорта в CSV: {output_path}")
        path = Path(output_path)
        if not path.suffix:
            path = path.with_suffix(".csv")

        headers = [
            "ID", "Title", "Priority", "Preconditions",
            "Steps", "Expected Result", "Test Type", "Technique", "Requirement"
        ]

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL)
            writer.writerow(headers)

            for result in results:
                req_text = result.requirement_text[:100] + "..." if len(result.requirement_text) > 100 else result.requirement_text

                for tc in result.test_cases:
                    preconditions = " | ".join(tc.preconditions) if tc.preconditions else ""
                    steps = " | ".join(f"{s['step']}. {s['action']}" for s in tc.steps) if tc.steps else ""

                    # Санитизируем все значения для защиты от formula injection
                    row = [
                        sanitize_for_excel(tc.id),
                        sanitize_for_excel(tc.title),
                        sanitize_for_excel(tc.priority),
                        sanitize_for_excel(preconditions),
                        sanitize_for_excel(steps),
                        sanitize_for_excel(tc.expected_result),
                        sanitize_for_excel(tc.test_type),
                        sanitize_for_excel(tc.technique),
                        sanitize_for_excel(req_text)
                    ]
                    writer.writerow(row)

        logger.info(f"CSV файл сохранен: {path}")
        return str(path)
