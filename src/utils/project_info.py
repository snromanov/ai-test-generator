#!/usr/bin/env python3
"""
Динамическое описание проекта AI Test Generator.
Собирает и предоставляет информацию о структуре, возможностях и состоянии проекта.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ProjectInfo:
    """Класс для динамического получения информации о проекте."""

    def __init__(self, project_root: Optional[Path] = None):
        """
        Инициализация с автоопределением корневой директории проекта.

        Args:
            project_root: Путь к корню проекта. Если None, определяется автоматически.
        """
        if project_root is None:
            # Определяем корень проекта относительно текущего файла
            self.project_root = Path(__file__).parent.parent.parent
        else:
            self.project_root = Path(project_root)

        self.src_dir = self.project_root / "src"

    def get_project_name(self) -> str:
        """Возвращает название проекта."""
        return "AI Test Generator"

    def get_version(self) -> str:
        """Возвращает версию проекта."""
        return "1.0.0"

    def get_description(self) -> str:
        """Возвращает описание проекта."""
        return (
            "Инструмент для автоматической генерации тест-кейсов на основе требований "
            "с использованием AI и передовых QA практик."
        )

    def get_features(self) -> List[str]:
        """Возвращает список основных возможностей проекта."""
        return [
            "Генерация тест-кейсов через CLI агенты (Claude Code, Qwen Code, Cursor)",
            "Загрузка требований из Confluence",
            "Загрузка требований из текстовых файлов",
            "Применение техник тест-дизайна (EP, BVA, Decision Table и др.)",
            "State Management для сохранения контекста",
            "Экспорт результатов в Excel и CSV форматы",
            "Промпты для CLI агентов с QA методологией"
        ]

    def get_test_design_techniques(self) -> Dict[str, str]:
        """Возвращает доступные техники тест-дизайна."""
        return {
            "equivalence_partitioning": "Эквивалентное разбиение",
            "boundary_value": "Анализ граничных значений",
            "decision_table": "Таблицы решений",
            "state_transition": "Переходы состояний",
            "use_case": "Варианты использования",
            "pairwise": "Попарное тестирование",
            "error_guessing": "Предугадывание ошибок"
        }

    def get_supported_agents(self) -> List[str]:
        """Возвращает список поддерживаемых CLI агентов."""
        return ["claude_code", "qwen_code", "cursor", "aider"]

    def get_export_formats(self) -> List[str]:
        """Возвращает поддерживаемые форматы экспорта."""
        return ["excel", "csv", "both"]

    def scan_modules(self) -> Dict[str, List[str]]:
        """Сканирует структуру проекта и возвращает список модулей."""
        modules = {}

        if not self.src_dir.exists():
            return modules

        for item in self.src_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                module_files = []
                for py_file in item.glob("*.py"):
                    if not py_file.name.startswith("_"):
                        module_files.append(py_file.stem)
                if module_files:
                    modules[item.name] = module_files

        return modules

    def count_python_files(self) -> int:
        """Подсчитывает количество Python файлов в проекте."""
        if not self.src_dir.exists():
            return 0
        return len(list(self.src_dir.rglob("*.py")))

    def count_lines_of_code(self) -> int:
        """Подсчитывает количество строк кода (приблизительно)."""
        total_lines = 0

        if not self.src_dir.exists():
            return 0

        for py_file in self.src_dir.rglob("*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    total_lines += sum(1 for line in f if line.strip())
            except Exception:
                continue

        return total_lines

    def get_dependencies(self) -> List[str]:
        """Читает и возвращает список зависимостей из requirements.txt."""
        requirements_file = self.project_root / "requirements.txt"
        dependencies = []

        if requirements_file.exists():
            try:
                with open(requirements_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        # Пропускаем комментарии и пустые строки
                        if line and not line.startswith("#"):
                            dependencies.append(line)
            except Exception:
                pass

        return dependencies

    def get_project_structure(self) -> Dict[str, any]:
        """Возвращает структуру проекта."""
        structure = {}

        if not self.src_dir.exists():
            return structure

        for item in self.src_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                structure[item.name] = [
                    f.name for f in item.iterdir()
                    if f.is_file() and f.suffix == ".py"
                ]

        return structure

    def get_cli_commands(self) -> List[Dict[str, str]]:
        """Возвращает список доступных CLI команд."""
        return [
            {
                "command": "confluence",
                "description": "Генерирует тесты из страницы Confluence",
                "usage": "python main.py confluence <PAGE_ID>"
            },
            {
                "command": "file",
                "description": "Генерирует тесты из файла с требованиями",
                "usage": "python main.py file <FILE_PATH>"
            },
            {
                "command": "interactive",
                "description": "Интерактивный режим ввода требований",
                "usage": "python main.py interactive"
            },
            {
                "command": "techniques",
                "description": "Показывает доступные техники тест-дизайна",
                "usage": "python main.py techniques"
            }
        ]

    def get_full_info(self) -> Dict[str, any]:
        """Собирает и возвращает полную информацию о проекте."""
        return {
            "name": self.get_project_name(),
            "version": self.get_version(),
            "description": self.get_description(),
            "features": self.get_features(),
            "test_design_techniques": self.get_test_design_techniques(),
            "supported_providers": self.get_supported_agents(),
            "export_formats": self.get_export_formats(),
            "modules": self.scan_modules(),
            "python_files_count": self.count_python_files(),
            "lines_of_code": self.count_lines_of_code(),
            "dependencies": self.get_dependencies(),
            "structure": self.get_project_structure(),
            "cli_commands": self.get_cli_commands(),
            "timestamp": datetime.now().isoformat()
        }

    def print_summary(self):
        """Выводит красивое резюме проекта через логирование."""
        logger.info("=" * 80)
        logger.info(f"  {self.get_project_name()} v{self.get_version()}")
        logger.info("=" * 80)
        logger.info("")
        logger.info("📝 Описание:")
        logger.info(f"  {self.get_description()}")
        logger.info("")
        
        logger.info("✨ Основные возможности:")
        for i, feature in enumerate(self.get_features(), 1):
            logger.info(f"  {i}. {feature}")
        logger.info("")
        
        logger.info("🤖 Поддерживаемые LLM провайдеры:")
        logger.info(f"  {', '.join(self.get_supported_agents())}")
        logger.info("")
        
        logger.info(f"🧪 Техники тест-дизайна ({len(self.get_test_design_techniques())}):")
        for tech_id, tech_name in self.get_test_design_techniques().items():
            logger.info(f"  • {tech_name} ({tech_id})")
        logger.info("")
        
        logger.info("📦 Структура проекта:")
        for module_name, files in self.scan_modules().items():
            logger.info(f"  • {module_name}/")
            for file in files:
                logger.info(f"    - {file}.py")
        logger.info("")
        
        logger.info("📊 Статистика:")
        logger.info(f"  • Python файлов: {self.count_python_files()}")
        logger.info(f"  • Строк кода: {self.count_lines_of_code()}")
        logger.info(f"  • Зависимостей: {len(self.get_dependencies())}")
        logger.info("")
        
        logger.info("💻 CLI команды:")
        for cmd in self.get_cli_commands():
            logger.info(f"  • {cmd['command']}: {cmd['description']}")
            logger.info(f"    {cmd['usage']}")
        logger.info("")
        
        logger.info("📤 Форматы экспорта:")
        logger.info(f"  {', '.join(self.get_export_formats())}")
        logger.info("")
        logger.info("=" * 80)

    def export_to_dict(self) -> Dict:
        """Экспортирует всю информацию в словарь."""
        return self.get_full_info()

    def export_to_json(self, output_file: Optional[Path] = None) -> str:
        """
        Экспортирует информацию о проекте в JSON формат.
        
        Args:
            output_file: Путь к файлу для сохранения. Если None, возвращает JSON строку.
            
        Returns:
            JSON строка с информацией о проекте.
        """
        import json
        
        logger.debug("Сбор информации о проекте для экспорта в JSON")
        info = self.get_full_info()
        json_str = json.dumps(info, ensure_ascii=False, indent=2)
        
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(json_str)
            logger.info(f"Информация о проекте сохранена в: {output_path}")
        else:
            logger.debug("JSON информация подготовлена без сохранения в файл")
        
        return json_str


def main():
    """Точка входа для запуска скрипта напрямую."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Динамическое описание проекта AI Test Generator"
    )
    parser.add_argument(
        "--format",
        choices=["summary", "json"],
        default="summary",
        help="Формат вывода (summary или json)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Путь к файлу для сохранения (только для JSON формата)"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Уровень логирования"
    )
    
    args = parser.parse_args()
    
    # Настраиваем логирование с указанным уровнем
    global logger
    logger = setup_logger(__name__, log_level=args.log_level)
    
    logger.debug(f"Запуск с параметрами: format={args.format}, output={args.output}")
    
    try:
        project = ProjectInfo()
        
        if args.format == "summary":
            logger.debug("Генерация резюме проекта")
            project.print_summary()
        elif args.format == "json":
            logger.debug("Экспорт информации в JSON формат")
            json_output = project.export_to_json(args.output)
            if not args.output:
                # Для JSON вывода в консоль используем print
                print(json_output)
    except Exception as e:
        logger.exception(f"Ошибка при выполнении: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
