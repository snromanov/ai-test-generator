#!/usr/bin/env python3
"""
AI Test Generator - CLI для работы с CLI агентами.

Этот проект заточен под CLI агенты (Claude Code, Qwen Code, Cursor и др.),
которые сами генерируют тесты на основе промптов и современных QA методологий.
"""
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

load_dotenv()

from src.generators.test_case_generator import TestCaseGenerator
from src.agents.test_agent import GenerationResult, TestCase, RequirementAnalysis
from src.prompts.qa_prompts import get_cli_agent_prompt
from src.state.state_manager import StateManager, RequirementStatus
from src.parsers.structured_parser import StructuredRequirementParser, get_layer_display_name, get_component_display_name
from src.utils.cleanup import Cleanup
from src.utils.requirement_analyzer import RequirementAnalyzer
from src.utils.test_generator_helper import (
    TestGeneratorHelper,
    create_boundary_test_cases,
    create_equivalence_test_cases,
    create_file_upload_tests,
    create_calendar_tests,
    create_integration_test_case,
)
from src.utils.project_info import ProjectInfo
from src.utils.logger import setup_logger
from src.utils.input_validation import (
    validate_confluence_page_id,
    validate_file_path,
    validate_file_size,
    validate_requirement_length,
    validate_export_filename,
)

logger = setup_logger(__name__)


def _load_raw_requirements(
    dir_path: str,
    auto_detect: bool,
    sm: StateManager
) -> tuple[int, dict, dict, int]:
    is_valid, error = validate_file_path(dir_path, allow_absolute=True)
    if not is_valid:
        raise ValueError(f"Невалидный путь: {error}")

    root = Path(dir_path)
    if not root.exists() or not root.is_dir():
        raise ValueError("Папка не найдена")

    files = [
        p for p in root.iterdir()
        if p.is_file()
        and p.suffix.lower() in {".md", ".txt"}
        and p.name.lower() != "readme.md"
    ]
    if not files:
        raise ValueError("В папке нет файлов .md/.txt")

    parser = StructuredRequirementParser()
    total_requirements = 0
    layer_stats = {}
    component_stats = {}
    skipped_files = 0

    for file_path in sorted(files):
        is_valid, error = validate_file_size(file_path)
        if not is_valid:
            skipped_files += 1
            continue

        content = file_path.read_text(encoding="utf-8")
        parsed_requirements = parser.parse_multiple(content, auto_detect=auto_detect)

        for parsed in parsed_requirements:
            req = sm.add_requirement(
                text=parsed.raw_text or parsed.description,
                source="file",
                source_ref=str(file_path)
            )

            req_obj = sm.find_requirement_by_id(req.id)
            if req_obj:
                req_obj.layer = parsed.layer.value
                req_obj.component = parsed.component.value
                req_obj.tags = parsed.tags
                req_obj.title = parsed.title

            layer_name = parsed.layer.value
            component_name = parsed.component.value
            layer_stats[layer_name] = layer_stats.get(layer_name, 0) + 1
            component_stats[component_name] = component_stats.get(component_name, 0) + 1
            total_requirements += 1

    sm.save()
    return total_requirements, layer_stats, component_stats, skipped_files


def _extract_max_files(boundary_values: dict) -> int | None:
    for field, bounds in boundary_values.items():
        if bounds.get("type") == "count" and isinstance(bounds.get("max"), int):
            return bounds["max"]
        if field.lower() in {"фото", "photo", "photos", "файлы", "files", "file"}:
            if isinstance(bounds.get("max"), int):
                return bounds["max"]
    return None


def _extract_max_size_mb(boundary_values: dict) -> float | None:
    for field, bounds in boundary_values.items():
        if bounds.get("type") == "file_size_mb" and isinstance(bounds.get("max"), (int, float)):
            return bounds["max"]
        if field.lower() in {"file_size", "size", "размер"}:
            if isinstance(bounds.get("max"), (int, float)):
                return bounds["max"]
    return None


def _prepare_tests_from_state() -> int:
    helper = TestGeneratorHelper()
    analyzer = RequirementAnalyzer()
    total_added = 0

    for req_info in helper.get_pending_requirements():
        req_id = req_info["id"]
        req_text = helper.get_requirement_text(req_id)
        analysis = analyzer.analyze(req_text, req_id)
        helper.add_analysis(req_id=req_id, **analyzer.to_helper_format(analysis))

        base_tc_id = f"TC-{req_id.split('-')[1]}"
        text_lower = req_text.lower()

        for field, bounds in analysis.boundary_values.items():
            if bounds.get("type") == "file_size_mb":
                continue
            if bounds.get("type") == "count" and field.lower() in {"фото", "photo", "photos", "файлы", "files", "file"}:
                continue
            min_val = bounds.get("min")
            max_val = bounds.get("max")
            if isinstance(min_val, int) and isinstance(max_val, int) and min_val <= max_val:
                bva_tests = create_boundary_test_cases(
                    req_id=req_id,
                    base_tc_id=f"{base_tc_id}-{field.upper()}",
                    field_name=field,
                    min_value=min_val,
                    max_value=max_val,
                    valid_example=(min_val + max_val) // 2,
                    invalid_low=min_val - 1,
                    invalid_high=max_val + 1,
                    endpoint=analysis.endpoint or "N/A"
                )
                total_added += helper.add_test_cases_bulk(req_id, bva_tests)

        for field, classes in analysis.equivalence_classes.items():
            valid_values = classes.get("valid", [])
            invalid_values = classes.get("invalid", [])
            if valid_values or invalid_values:
                ep_tests = create_equivalence_test_cases(
                    req_id=req_id,
                    base_tc_id=f"{base_tc_id}-{field.upper()}",
                    field_name=field,
                    valid_values=valid_values,
                    invalid_values=invalid_values,
                    endpoint=analysis.endpoint or "N/A"
                )
                total_added += helper.add_test_cases_bulk(req_id, ep_tests)

        if "календар" in text_lower or "calendar" in text_lower:
            calendar_tests = create_calendar_tests(
                req_id=req_id,
                base_tc_id=base_tc_id,
                ui_element="calendar"
            )
            total_added += helper.add_test_cases_bulk(req_id, calendar_tests)

        if any(token in text_lower for token in ["фото", "файл", "upload", "photo", "file"]):
            max_files = _extract_max_files(analysis.boundary_values)
            max_size_mb = _extract_max_size_mb(analysis.boundary_values)
            if max_files is None and ("нескольк" in text_lower or "multiple" in text_lower):
                max_files = 10
            if max_files:
                upload_tests = create_file_upload_tests(
                    req_id=req_id,
                    base_tc_id=base_tc_id,
                    allowed_formats=["jpg", "png"],
                    max_size_mb=max_size_mb,
                    max_files=max_files,
                    ui_element="photo-upload"
                )
                total_added += helper.add_test_cases_bulk(req_id, upload_tests)

        if "llm_integration" in analysis.suggested_techniques:
            llm_tests = [
                create_integration_test_case(
                    base_tc_id=f"{base_tc_id}-LLM-001",
                    title="Получение тега от LLM при модерации идеи",
                    test_type="Positive",
                    technique="llm_integration",
                    tags=["llm", "integration"]
                ),
                create_integration_test_case(
                    base_tc_id=f"{base_tc_id}-LLM-002",
                    title="Некорректный ответ LLM → модерация без тегов",
                    test_type="Negative",
                    technique="llm_integration",
                    tags=["llm", "validation"]
                ),
                create_integration_test_case(
                    base_tc_id=f"{base_tc_id}-LLM-003",
                    title="Таймаут LLM → модерация без тегов",
                    test_type="Performance",
                    technique="llm_integration",
                    tags=["llm", "timeout"]
                ),
            ]
            total_added += helper.add_test_cases_bulk(req_id, llm_tests)

    return total_added


def _compute_layer_component_stats(session) -> tuple[dict, dict]:
    layer_stats: dict[str, int] = {}
    component_stats: dict[str, int] = {}
    for req in session.requirements:
        layer = getattr(req, "layer", "api") or "api"
        component = getattr(req, "component", "fullstack") or "fullstack"
        layer_stats[layer] = layer_stats.get(layer, 0) + 1
        component_stats[component] = component_stats.get(component, 0) + 1
    return layer_stats, component_stats


def _resolve_demo_file(name: str | None) -> Path | None:
    demo_dir = Path("demo")
    if not demo_dir.exists():
        click.echo(click.style("Директория demo не найдена", fg="red"))
        return None

    demos = list(demo_dir.glob("*.md"))
    if not demos:
        click.echo(click.style("Демо-файлы не найдены", fg="yellow"))
        return None

    if not name:
        click.echo("\nДоступные демо-требования:")
        for i, demo in enumerate(demos, 1):
            click.echo(f"  {i}. {demo.stem}")

        choice = click.prompt("\nВыберите номер или введите имя", type=str)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(demos):
                return demos[idx]
            click.echo("Неверный номер")
            return None
        except ValueError:
            selected = demo_dir / f"{choice}.md"
            if not selected.exists():
                click.echo(f"Файл {selected} не найден")
                return None
            return selected

    selected = demo_dir / f"{name}.md"
    if not selected.exists():
        selected = demo_dir / name
        if not selected.exists():
            click.echo(f"Демо {name} не найдено")
            return None
    return selected


def _run_raw_pipeline(
    dir_path: str,
    auto_detect: bool,
    no_backup: bool,
    agent_type: str | None,
    confirm: bool
) -> tuple[int, int, dict, dict, int] | None:
    if confirm and not click.confirm("Будут удалены state/кэш и очищены artifacts. Продолжить?"):
        click.echo("Операция отменена.")
        return None

    cleanup = Cleanup()
    cleanup.prepare_for_new_generation(backup=not no_backup)

    sm = StateManager()
    sm.create_session(agent_type=agent_type)

    total_requirements, layer_stats, component_stats, skipped_files = _load_raw_requirements(
        dir_path, auto_detect, sm
    )
    total_tests = _prepare_tests_from_state()
    return total_requirements, total_tests, layer_stats, component_stats, skipped_files


def _run_demo_pipeline(
    name: str | None,
    no_backup: bool,
    agent_type: str | None,
    confirm: bool
) -> tuple[int, int, dict, dict, int] | None:
    if confirm and not click.confirm("Будут удалены state/кэш и очищены artifacts. Продолжить?"):
        click.echo("Операция отменена.")
        return None

    selected = _resolve_demo_file(name)
    if selected is None:
        return None

    cleanup = Cleanup()
    cleanup.prepare_for_new_generation(backup=not no_backup)

    sm = StateManager()
    sm.create_session(agent_type=agent_type)

    is_valid, error = validate_file_size(selected)
    if not is_valid:
        click.echo(click.style(f"Невалидный файл: {error}", fg="red"))
        return None

    generator = TestCaseGenerator(state_manager=sm)
    requirements = generator.load_from_file(str(selected))

    if not requirements:
        click.echo(click.style("Требования не найдены", fg="yellow"))
        return None

    total_tests = _prepare_tests_from_state()
    session = sm.load()
    if session is None:
        click.echo(click.style("Сессия не найдена после загрузки", fg="red"))
        return None

    layer_stats, component_stats = _compute_layer_component_stats(session)
    return len(requirements), total_tests, layer_stats, component_stats, 0


def _print_raw_pipeline_summary(
    total_requirements: int,
    total_tests: int,
    layer_stats: dict,
    component_stats: dict,
    skipped_files: int
):
    click.echo(click.style(f"\nЗагружено {total_requirements} требований", fg="green"))
    click.echo(click.style(f"Подготовлено тест-кейсов: {total_tests}", fg="green"))
    if skipped_files:
        click.echo(click.style(f"Пропущено файлов: {skipped_files}", fg="yellow"))

    click.echo("\nСтатистика по слоям:")
    for layer, count in sorted(layer_stats.items()):
        display_name = get_layer_display_name(layer) if hasattr(layer, 'value') else layer.upper()
        click.echo(f"  {display_name}: {count}")

    click.echo("\nСтатистика по компонентам:")
    for component, count in sorted(component_stats.items()):
        color = {"backend": "blue", "frontend": "yellow", "fullstack": "green"}.get(component, "white")
        click.echo(f"  {click.style(component.capitalize(), fg=color)}: {count}")

    click.echo("\nТеперь вы можете:")
    click.echo("  python main.py state show")
    click.echo("  python main.py state export -f excel -o artifacts/test_cases --group-by-layer")


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """AI Test Generator - генерация тест-кейсов через CLI агентов."""
    pass


# =============================================================================
# Команды загрузки требований
# =============================================================================

@cli.command("load-confluence")
@click.argument("page_id")
def load_confluence(page_id: str):
    """Загружает требования из Confluence в state."""
    click.echo(f"Загрузка страницы Confluence: {page_id}")

    try:
        is_valid, error = validate_confluence_page_id(page_id)
        if not is_valid:
            click.echo(click.style(f"Невалидный ID страницы: {error}", fg="red"))
            return

        generator = TestCaseGenerator()
        requirements = generator.load_from_confluence(page_id)

        if not requirements:
            click.echo(click.style("Требования не найдены на странице", fg="yellow"))
            return

        click.echo(click.style(f"Загружено {len(requirements)} требований", fg="green"))
        click.echo("\nТеперь CLI агент может сгенерировать тесты:")
        click.echo("  python main.py state show")

    except Exception as e:
        logger.exception("Ошибка загрузки")
        click.echo(f"Ошибка: {e}", err=True)
        sys.exit(1)


@cli.command("load-file")
@click.argument("file_path", type=click.Path(exists=True))
def load_file(file_path: str):
    """Загружает требования из файла в state."""
    click.echo(f"Чтение файла: {file_path}")

    try:
        is_valid, error = validate_file_path(file_path, allow_absolute=True)
        if not is_valid:
            click.echo(click.style(f"Невалидный путь: {error}", fg="red"))
            return
        is_valid, error = validate_file_size(Path(file_path))
        if not is_valid:
            click.echo(click.style(f"Невалидный файл: {error}", fg="red"))
            return

        generator = TestCaseGenerator()
        requirements = generator.load_from_file(file_path)

        if not requirements:
            click.echo(click.style("Требования не найдены в файле", fg="yellow"))
            return

        click.echo(click.style(f"Загружено {len(requirements)} требований", fg="green"))
        click.echo("\nТеперь CLI агент может сгенерировать тесты:")
        click.echo("  python main.py state show")

    except Exception as e:
        logger.exception("Ошибка загрузки")
        click.echo(f"Ошибка: {e}", err=True)
        sys.exit(1)


@cli.command("load-demo")
@click.option("--name", "-n", help="Имя демо-файла (например, petstore)")
def load_demo(name: str):
    """Загружает демонстрационные требования."""
    selected = _resolve_demo_file(name)
    if selected is None:
        return

    click.echo(f"Загрузка демо-требований: {selected.name}")
    
    try:
        is_valid, error = validate_file_size(selected)
        if not is_valid:
            click.echo(click.style(f"Невалидный файл: {error}", fg="red"))
            return

        generator = TestCaseGenerator()
        requirements = generator.load_from_file(str(selected))

        if not requirements:
            click.echo(click.style("Требования не найдены", fg="yellow"))
            return

        click.echo(click.style(f"Загружено {len(requirements)} демо-требований", fg="green"))
        click.echo("\nТеперь вы можете просмотреть их:")
        click.echo("  python main.py state show")

    except Exception as e:
        logger.exception("Ошибка загрузки демо")
        click.echo(f"Ошибка: {e}", err=True)
        sys.exit(1)


@cli.command("load-structured")
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--auto-detect/--no-auto-detect", default=True,
              help="Автоматически определять layer/component по ключевым словам")
def load_structured(file_path: str, auto_detect: bool):
    """Загружает структурированные требования с тегами [Back]/[Front]/[API]/[UI]."""
    click.echo(f"Загрузка структурированных требований: {file_path}")

    try:
        is_valid, error = validate_file_path(file_path, allow_absolute=True)
        if not is_valid:
            click.echo(click.style(f"Невалидный путь: {error}", fg="red"))
            return
        is_valid, error = validate_file_size(Path(file_path))
        if not is_valid:
            click.echo(click.style(f"Невалидный файл: {error}", fg="red"))
            return

        # Читаем файл
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Парсим структурированные требования
        parser = StructuredRequirementParser()
        parsed_requirements = parser.parse_multiple(content)

        if not parsed_requirements:
            click.echo(click.style("Требования не найдены в файле", fg="yellow"))
            return

        # Создаем или загружаем сессию
        sm = StateManager()
        session = sm.get_or_create_session(agent_type="cli_agent")

        # Статистика по слоям и компонентам
        layer_stats = {}
        component_stats = {}

        # Добавляем требования в state с расширенными метаданными
        for parsed in parsed_requirements:
            req = sm.add_requirement(
                text=parsed.raw_text or parsed.description,
                source="file",
                source_ref=file_path
            )

            # Обновляем расширенные поля
            req_obj = sm.find_requirement_by_id(req.id)
            if req_obj:
                req_obj.layer = parsed.layer.value
                req_obj.component = parsed.component.value
                req_obj.tags = parsed.tags
                req_obj.title = parsed.title

            # Собираем статистику
            layer_name = parsed.layer.value
            component_name = parsed.component.value
            layer_stats[layer_name] = layer_stats.get(layer_name, 0) + 1
            component_stats[component_name] = component_stats.get(component_name, 0) + 1

        sm.save()

        # Выводим результат
        click.echo(click.style(f"\nЗагружено {len(parsed_requirements)} требований", fg="green"))

        click.echo("\nСтатистика по слоям:")
        for layer, count in sorted(layer_stats.items()):
            display_name = get_layer_display_name(layer) if hasattr(layer, 'value') else layer.upper()
            click.echo(f"  {display_name}: {count}")

        click.echo("\nСтатистика по компонентам:")
        for component, count in sorted(component_stats.items()):
            color = {"backend": "blue", "frontend": "yellow", "fullstack": "green"}.get(component, "white")
            click.echo(f"  {click.style(component.capitalize(), fg=color)}: {count}")

        click.echo("\nТеперь вы можете:")
        click.echo("  python main.py state show")
        click.echo("  python main.py state export -f excel -o artifacts/test_cases --group-by-layer")

    except Exception as e:
        logger.exception("Ошибка загрузки структурированных требований")
        click.echo(f"Ошибка: {e}", err=True)
        sys.exit(1)


@cli.command("load-raw")
@click.option("--dir", "dir_path", default="requirements/raw",
              help="Папка с сырыми требованиями (.md/.txt)")
@click.option("--auto-detect/--no-auto-detect", default=True,
              help="Автоматически определять layer/component по ключевым словам")
def load_raw(dir_path: str, auto_detect: bool):
    """Загружает сырые требования из папки requirements/raw."""
    click.echo(f"Загрузка сырых требований из: {dir_path}")

    try:
        sm = StateManager()
        sm.get_or_create_session(agent_type="cli_agent")
        total_requirements, layer_stats, component_stats, skipped_files = _load_raw_requirements(
            dir_path, auto_detect, sm
        )

        if total_requirements == 0:
            click.echo(click.style("Требования не найдены", fg="yellow"))
            return

        click.echo(click.style(f"\nЗагружено {total_requirements} требований", fg="green"))
        if skipped_files:
            click.echo(click.style(f"Пропущено файлов: {skipped_files}", fg="yellow"))

        click.echo("\nСтатистика по слоям:")
        for layer, count in sorted(layer_stats.items()):
            display_name = get_layer_display_name(layer) if hasattr(layer, 'value') else layer.upper()
            click.echo(f"  {display_name}: {count}")

        click.echo("\nСтатистика по компонентам:")
        for component, count in sorted(component_stats.items()):
            color = {"backend": "blue", "frontend": "yellow", "fullstack": "green"}.get(component, "white")
            click.echo(f"  {click.style(component.capitalize(), fg=color)}: {count}")

        click.echo("\nТеперь вы можете:")
        click.echo("  python main.py state show")
        click.echo("  python main.py state export -f excel -o artifacts/test_cases --group-by-layer")

    except Exception as e:
        logger.exception("Ошибка загрузки сырых требований")
        click.echo(f"Ошибка: {e}", err=True)
        sys.exit(1)


@cli.command("rebuild-raw")
@click.option("--dir", "dir_path", default="requirements/raw",
              help="Папка с сырыми требованиями (.md/.txt)")
@click.option("--auto-detect/--no-auto-detect", default=True,
              help="Автоматически определять layer/component по ключевым словам")
@click.option("--no-backup", is_flag=True, help="Не делать бэкап artifacts")
@click.option("--agent", "-a", type=str, default="local_agent",
              help="Имя локального агента (например: codex, qwen, claude)")
def rebuild_raw(dir_path: str, auto_detect: bool, no_backup: bool, agent: str):
    """Очищает проект, загружает сырые требования и готовит тесты."""
    try:
        result = _run_raw_pipeline(
            dir_path=dir_path,
            auto_detect=auto_detect,
            no_backup=no_backup,
            agent_type=agent,
            confirm=True
        )
        if result is None:
            return
        total_requirements, total_tests, layer_stats, component_stats, skipped_files = result

        _print_raw_pipeline_summary(
            total_requirements=total_requirements,
            total_tests=total_tests,
            layer_stats=layer_stats,
            component_stats=component_stats,
            skipped_files=skipped_files
        )

    except Exception as e:
        logger.exception("Ошибка rebuild-raw")
        click.echo(f"Ошибка: {e}", err=True)
        sys.exit(1)


# =============================================================================
# Информационные команды
# =============================================================================

@cli.command()
def techniques():
    """Показывает доступные техники тест-дизайна."""
    click.echo("\nДоступные техники тест-дизайна:\n")

    click.echo(click.style("== Базовые техники ==", fg="cyan", bold=True))
    techniques_info = [
        ("equivalence_partitioning", "Эквивалентное разбиение",
         "Разделение входных данных на классы эквивалентности"),
        ("boundary_value", "Анализ граничных значений",
         "Тестирование значений на границах диапазонов"),
        ("decision_table", "Таблицы решений",
         "Тестирование комбинаций условий и действий"),
        ("state_transition", "Переходы состояний",
         "Тестирование переходов между состояниями системы"),
        ("use_case", "Варианты использования",
         "Тестирование сценариев использования"),
        ("pairwise", "Попарное тестирование",
         "Минимальный набор тестов для покрытия пар значений"),
        ("error_guessing", "Предугадывание ошибок",
         "Тесты на основе типичных ошибок и опыта")
    ]

    for tech_id, name, description in techniques_info:
        click.echo(f"  {click.style(tech_id, fg='green', bold=True)}")
        click.echo(f"    {name}")
        click.echo(f"    {click.style(description, dim=True)}")
        click.echo()

    click.echo(click.style("== UI техники ==", fg="cyan", bold=True))
    ui_techniques = [
        ("ui_calendar", "Тестирование календарей",
         "Выбор дат, навигация, граничные значения, диапазоны"),
        ("ui_form", "Тестирование форм",
         "Валидация полей, состояния, submit, автосохранение"),
        ("ui_file_upload", "Загрузка файлов",
         "Drag-drop, форматы, размеры, прогресс, превью"),
    ]

    for tech_id, name, description in ui_techniques:
        click.echo(f"  {click.style(tech_id, fg='yellow', bold=True)}")
        click.echo(f"    {name}")
        click.echo(f"    {click.style(description, dim=True)}")
        click.echo()

    click.echo(click.style("== Интеграционные техники ==", fg="cyan", bold=True))
    integration_techniques = [
        ("llm_integration", "LLM интеграции",
         "Schema validation, timeout, injection protection, качество"),
        ("backend_frontend_integration", "Backend-Frontend",
         "API contract, data flow, error propagation, auth"),
    ]

    for tech_id, name, description in integration_techniques:
        click.echo(f"  {click.style(tech_id, fg='magenta', bold=True)}")
        click.echo(f"    {name}")
        click.echo(f"    {click.style(description, dim=True)}")
        click.echo()


@cli.command("agent-prompt")
@click.option("--save", "-s", type=click.Path(), help="Сохранить промпт в файл")
def agent_prompt(save: str):
    """Показывает промпт для CLI агента."""
    prompt = get_cli_agent_prompt()

    if save:
        with open(save, "w", encoding="utf-8") as f:
            f.write(prompt)
        click.echo(f"Промпт сохранен в: {click.style(save, fg='green')}")
        return

    click.echo(click.style("\n=== ПРОМПТ ДЛЯ CLI АГЕНТА ===\n", fg='cyan', bold=True))
    click.echo(prompt)
    click.echo(click.style("\n=== КОНЕЦ ПРОМПТА ===\n", fg='cyan', bold=True))


@cli.group("agent")
def agent_group():
    """Команды локального агента."""
    pass


@agent_group.command("pipeline-raw")
@click.option("--agent", "-a", type=str, default="local_agent",
              help="Имя локального агента (например: codex, qwen, claude)")
@click.option("--dir", "dir_path", default="requirements/raw",
              help="Папка с сырыми требованиями (.md/.txt)")
@click.option("--auto-detect/--no-auto-detect", default=True,
              help="Автоматически определять layer/component по ключевым словам")
@click.option("--no-backup", is_flag=True, help="Не делать бэкап artifacts")
@click.option("--yes", is_flag=True, help="Не спрашивать подтверждение")
def agent_pipeline_raw(
    agent: str,
    dir_path: str,
    auto_detect: bool,
    no_backup: bool,
    yes: bool
):
    """Запускает полный pipeline: очистка -> raw -> автогенерация тестов."""
    try:
        result = _run_raw_pipeline(
            dir_path=dir_path,
            auto_detect=auto_detect,
            no_backup=no_backup,
            agent_type=agent,
            confirm=not yes
        )
        if result is None:
            return
        total_requirements, total_tests, layer_stats, component_stats, skipped_files = result
        _print_raw_pipeline_summary(
            total_requirements=total_requirements,
            total_tests=total_tests,
            layer_stats=layer_stats,
            component_stats=component_stats,
            skipped_files=skipped_files
        )
    except Exception as e:
        logger.exception("Ошибка agent pipeline-raw")
        click.echo(f"Ошибка: {e}", err=True)
        sys.exit(1)


@agent_group.command("pipeline-demo")
@click.option("--agent", "-a", type=str, default="local_agent",
              help="Имя локального агента (например: codex, qwen, claude)")
@click.option("--name", "-n", help="Имя демо-файла (например, petstore)")
@click.option("--no-backup", is_flag=True, help="Не делать бэкап artifacts")
@click.option("--yes", is_flag=True, help="Не спрашивать подтверждение")
def agent_pipeline_demo(
    agent: str,
    name: str | None,
    no_backup: bool,
    yes: bool
):
    """Запускает полный pipeline: очистка -> demo -> автогенерация тестов."""
    try:
        result = _run_demo_pipeline(
            name=name,
            no_backup=no_backup,
            agent_type=agent,
            confirm=not yes
        )
        if result is None:
            return
        total_requirements, total_tests, layer_stats, component_stats, skipped_files = result
        _print_raw_pipeline_summary(
            total_requirements=total_requirements,
            total_tests=total_tests,
            layer_stats=layer_stats,
            component_stats=component_stats,
            skipped_files=skipped_files
        )
    except Exception as e:
        logger.exception("Ошибка agent pipeline-demo")
        click.echo(f"Ошибка: {e}", err=True)
        sys.exit(1)


@cli.command("info")
@click.option("--format", "-f", type=click.Choice(["text", "json"]), default="text")
def project_info(format: str):
    """Показывает информацию о проекте (для CLI агента)."""
    info = ProjectInfo()

    if format == "json":
        click.echo(info.export_to_json())
    else:
        # Выводим структуру для промпта
        click.echo("\n## Структура проекта\n")
        click.echo("```")
        for module, files in info.get_project_structure().items():
            click.echo(f"src/{module}/")
            for f in files:
                click.echo(f"  └── {f}")
        click.echo("```")

        click.echo(f"\n**Python файлов:** {info.count_python_files()}")
        click.echo(f"**Строк кода:** {info.count_lines_of_code()}")


# =============================================================================
# Команды State Manager
# =============================================================================

@cli.group()
def state():
    """Управление состоянием сессии генерации."""
    pass


@state.command("show")
@click.option("--format", "-f", type=click.Choice(["text", "json"]), default="text")
def state_show(format: str):
    """Показывает текущее состояние сессии."""
    sm = StateManager()
    session = sm.load()

    if not session:
        click.echo(click.style("Активная сессия не найдена.", fg="yellow"))
        click.echo("Создайте новую: python main.py state new")
        return

    if format == "json":
        import json
        click.echo(json.dumps(sm.get_summary(), ensure_ascii=False, indent=2))
    else:
        click.echo(sm.get_context_for_agent())


@state.command("new")
@click.option("--agent", "-a", type=str,
              help="Имя локального агента (например: codex, qwen, claude)")
def state_new(agent: str):
    """Создает новую сессию генерации."""
    sm = StateManager()

    existing = sm.load()
    if existing:
        if not click.confirm(f"Существует сессия {existing.session_id}. Перезаписать?"):
            return

    session = sm.create_session(agent_type=agent)
    click.echo(click.style(f"Создана сессия: {session.session_id}", fg="green"))
    if agent:
        click.echo(f"Агент: {agent}")


@state.command("add")
@click.argument("text")
def state_add(text: str):
    """Добавляет требование в текущую сессию."""
    sm = StateManager()
    session = sm.load()

    if not session:
        click.echo(click.style("Сессия не найдена. Создайте: python main.py state new", fg="red"))
        return

    is_valid, error = validate_requirement_length(text)
    if not is_valid:
        click.echo(click.style(f"Невалидное требование: {error}", fg="red"))
        return

    req = sm.add_requirement(text, source="manual")
    click.echo(click.style(f"Добавлено требование: {req.id}", fg="green"))


@state.command("context")
def state_context():
    """Выводит контекст для CLI агента."""
    sm = StateManager()
    sm.load()
    click.echo(sm.get_context_for_agent())


@state.command("note")
@click.argument("text")
def state_note(text: str):
    """Добавляет заметку к сессии."""
    sm = StateManager()
    session = sm.load()

    if not session:
        click.echo(click.style("Сессия не найдена.", fg="red"))
        return

    sm.add_note(text)
    click.echo(click.style("Заметка добавлена.", fg="green"))


@state.command("feedback")
@click.argument("req_id")
@click.argument("text")
def state_feedback(req_id: str, text: str):
    """Добавляет замечание пользователя по требованию."""
    sm = StateManager()
    session = sm.load()

    if not session:
        click.echo(click.style("Сессия не найдена.", fg="red"))
        return

    req = sm.find_requirement_by_id(req_id)
    if not req:
        click.echo(click.style(f"Требование не найдено: {req_id}", fg="red"))
        return

    sm.add_requirement_feedback(req_id, text)
    click.echo(click.style("Замечание добавлено.", fg="green"))


@state.command("clear")
@click.confirmation_option(prompt="Удалить состояние?")
def state_clear():
    """Удаляет текущее состояние."""
    sm = StateManager()
    sm.clear()
    click.echo(click.style("Состояние очищено.", fg="green"))


@state.command("resume")
def state_resume():
    """Показывает, что нужно сделать дальше."""
    sm = StateManager()
    session = sm.load()

    if not session:
        click.echo(click.style("Сессия не найдена.", fg="yellow"))
        return

    pending = sm.get_pending_requirements()

    click.echo(click.style("\n=== RESUME ===\n", fg="cyan", bold=True))
    click.echo(f"Текущий шаг: {session.progress.current_step}")
    click.echo(f"Последнее действие: {session.progress.last_action or 'нет'}")
    click.echo()

    if pending:
        click.echo(f"Ожидают обработки {len(pending)} требований:")
        for req in pending[:5]:
            click.echo(f"  - {req.id}: {req.text[:50]}...")
        click.echo()
        click.echo("Следующий шаг: проанализировать требования и сгенерировать тесты")
    else:
        click.echo("Все требования обработаны.")
        review_count = sum(
            1 for r in session.requirements
            for tc in r.test_cases if tc.status == "draft"
        )
        if review_count:
            click.echo(f"Тестов на ревью: {review_count}")
        else:
            click.echo("Можно экспортировать результаты:")
            click.echo("  python main.py state export -f excel -o artifacts/test_cases")


@state.command("export")
@click.option("--output", "-o", default="artifacts/test_cases", help="Имя выходного файла")
@click.option("--format", "-f", type=click.Choice(["excel", "csv", "both"]), default="excel")
@click.option("--group-by-layer", is_flag=True, default=False,
              help="Группировать тест-кейсы по слоям (api, ui, integration, e2e)")
def state_export(output: str, format: str, group_by_layer: bool):
    """Экспортирует результаты из state."""
    sm = StateManager()
    session = sm.load()

    if not session:
        click.echo(click.style("Сессия не найдена.", fg="red"))
        return

    if not session.requirements:
        click.echo(click.style("Нет требований для экспорта.", fg="yellow"))
        return

    output_path = Path(output)
    is_valid, error = validate_export_filename(output_path.name)
    if not is_valid:
        click.echo(click.style(f"Невалидное имя файла: {error}", fg="red"))
        return
    is_valid, error = validate_file_path(str(output_path), allow_absolute=True)
    if not is_valid:
        click.echo(click.style(f"Невалидный путь экспорта: {error}", fg="red"))
        return

    # Конвертируем state в GenerationResult
    results = []
    for req in session.requirements:
        analysis = RequirementAnalysis()
        if req.analysis:
            analysis = RequirementAnalysis(
                inputs=req.analysis.inputs,
                outputs=req.analysis.outputs,
                business_rules=req.analysis.business_rules,
                states=req.analysis.states
            )

        test_cases = []
        for tc in req.test_cases:
            test_cases.append(TestCase(
                id=tc.id,
                title=tc.title,
                priority=tc.priority,
                preconditions=tc.preconditions,
                steps=tc.steps,
                expected_result=tc.expected_result,
                test_type=tc.test_type,
                technique=tc.technique,
                # Новые поля
                layer=getattr(tc, 'layer', 'api') or 'api',
                component=getattr(tc, 'component', 'fullstack') or 'fullstack',
                tags=getattr(tc, 'tags', []) or [],
                ui_element=getattr(tc, 'ui_element', None),
                api_endpoint=getattr(tc, 'api_endpoint', None)
            ))

        results.append(GenerationResult(
            requirement_text=req.text,
            analysis=analysis,
            test_cases=test_cases,
            tokens_used=0,
            model="cli_agent"
        ))

    generator = TestCaseGenerator()

    if format in ("excel", "both"):
        path = generator.export_to_excel(results, output, group_by_layer=group_by_layer)
        click.echo(f"Excel: {click.style(path, fg='green')}")
        if group_by_layer:
            click.echo("  (с группировкой по слоям: API, UI, Integration, E2E)")

    if format in ("csv", "both"):
        path = generator.export_to_csv(results, output)
        click.echo(f"CSV: {click.style(path, fg='green')}")

    sm.update_progress(step="completed", action=f"exported to {format}")


# =============================================================================
# Unified Generate Command
# =============================================================================

@cli.command("generate")
@click.option("--source", "-s", default="raw",
              help="Источник требований: raw, demo/petstore, file.md, confluence:PAGE_ID")
@click.option("--output", "-o", default="artifacts/test_cases",
              help="Путь для экспорта (без расширения)")
@click.option("--format", "-f", type=click.Choice(["excel", "csv", "both"]), default="excel",
              help="Формат экспорта")
@click.option("--agent", "-a", default="local_agent",
              help="Тип агента (local_agent, codex, qwen, claude)")
@click.option("--no-backup", is_flag=True,
              help="Не создавать бэкап artifacts")
@click.option("--no-clean", is_flag=True,
              help="Не очищать state перед генерацией")
@click.option("--no-group", is_flag=True,
              help="Не группировать тесты по слоям в Excel")
@click.option("--no-auto-detect", is_flag=True,
              help="Не использовать автоопределение layer/component")
def generate(
    source: str,
    output: str,
    format: str,
    agent: str,
    no_backup: bool,
    no_clean: bool,
    no_group: bool,
    no_auto_detect: bool
):
    """
    Единая команда для генерации тест-кейсов.
    
    Выполняет полный цикл: загрузка → анализ → генерация → экспорт
    
    Примеры:
    \b
      # Из requirements/raw (по умолчанию)
      python main.py generate
    
    \b
      # Из демо-файла
      python main.py generate --source demo/petstore
    
    \b
      # Из конкретного файла
      python main.py generate --source my_requirements.md
    
    \b
      # Из Confluence
      python main.py generate --source confluence:123456
    
    \b
      # С кастомными настройками
      python main.py generate --source raw --output my_tests --format both
    """
    from src.pipelines.orchestrator import create_orchestrator_from_args
    
    try:
        click.echo(click.style("\n=== AI Test Generator ===\n", fg="cyan", bold=True))
        click.echo(f"Источник: {click.style(source, fg='yellow')}")
        click.echo(f"Агент: {agent}")
        click.echo(f"Формат: {format}")
        click.echo()
        
        # Создаем orchestrator
        orchestrator = create_orchestrator_from_args(
            source=source,
            output=output,
            format=format,
            agent=agent,
            no_backup=no_backup,
            no_clean=no_clean,
            no_group=no_group,
            no_auto_detect=no_auto_detect
        )
        
        # Запускаем pipeline
        result = orchestrator.run()
        
        if not result.success:
            click.echo(click.style(f"\nОшибка: {result.error_message}", fg="red"))
            sys.exit(1)
        
        # Выводим результаты
        click.echo(click.style("\n=== Результаты генерации ===\n", fg="green", bold=True))
        click.echo(f"✓ Загружено требований: {click.style(str(result.requirements_loaded), fg='green', bold=True)}")
        click.echo(f"✓ Сгенерировано тестов: {click.style(str(result.tests_generated), fg='green', bold=True)}")
        
        if result.skipped_files > 0:
            click.echo(f"⚠ Пропущено файлов: {click.style(str(result.skipped_files), fg='yellow')}")
        
        if result.layer_stats:
            click.echo("\nСтатистика по слоям:")
            for layer, count in sorted(result.layer_stats.items()):
                display_name = get_layer_display_name(layer) if hasattr(layer, 'value') else layer.upper()
                click.echo(f"  {display_name}: {count}")
        
        if result.component_stats:
            click.echo("\nСтатистика по компонентам:")
            for component, count in sorted(result.component_stats.items()):
                color = {"backend": "blue", "frontend": "yellow", "fullstack": "green"}.get(component, "white")
                click.echo(f"  {click.style(component.capitalize(), fg=color)}: {count}")
        
        click.echo("\nЭкспортированные файлы:")
        for path in result.export_paths:
            click.echo(f"  {click.style(path, fg='green', bold=True)}")
        
        click.echo(click.style("\n✓ Генерация завершена успешно!\n", fg="green", bold=True))
        
    except Exception as e:
        logger.exception("Ошибка генерации")
        click.echo(click.style(f"\nОшибка: {e}", fg="red"))
        sys.exit(1)


# =============================================================================
# User-friendly short aliases
# =============================================================================

@cli.command("gen")
@click.option("--source", "-s", default="raw", help="Источник: raw, demo/NAME, file.md")
@click.option("--output", "-o", default="artifacts/test_cases", help="Путь экспорта")
@click.option("--format", "-f", type=click.Choice(["excel", "csv", "both"]), default="both")
@click.pass_context
def gen(ctx, source: str, output: str, format: str):
    """
    Короткий алиас для generate.

    Примеры:
    \b
      python main.py gen                    # из raw, excel+csv
      python main.py gen -s demo/petstore   # из демо
      python main.py gen -o my_tests        # в my_tests.xlsx
    """
    ctx.invoke(generate, source=source, output=output, format=format)


@cli.command("show")
@click.option("--format", "-f", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def show(ctx, format: str):
    """Короткий алиас для state show."""
    ctx.invoke(state_show, format=format)


@cli.command("export")
@click.option("--output", "-o", default="artifacts/test_cases", help="Путь экспорта")
@click.option("--format", "-f", type=click.Choice(["excel", "csv", "both"]), default="both")
@click.option("--group-by-layer", "-g", is_flag=True, default=True, help="Группировать по слоям")
@click.pass_context
def export_cmd(ctx, output: str, format: str, group_by_layer: bool):
    """
    Короткий алиас для state export.

    Примеры:
    \b
      python main.py export                 # excel+csv в artifacts/
      python main.py export -o my_tests     # в my_tests.xlsx/.csv
      python main.py export -f excel        # только excel
    """
    ctx.invoke(state_export, output=output, format=format, group_by_layer=group_by_layer)


@cli.command("stats")
def stats():
    """Показывает краткую статистику текущей сессии."""
    sm = StateManager()
    session = sm.load()

    if not session:
        click.echo(click.style("Сессия не найдена.", fg="yellow"))
        click.echo("Запустите: python main.py gen")
        return

    total_reqs = len(session.requirements)
    completed_reqs = sum(1 for r in session.requirements if r.status.value == 'completed')
    total_tests = sum(len(r.test_cases) for r in session.requirements)

    # Статистика по слоям
    layer_counts = {}
    for req in session.requirements:
        for tc in req.test_cases:
            layer = getattr(tc, 'layer', 'api') or 'api'
            layer_counts[layer] = layer_counts.get(layer, 0) + 1

    click.echo(click.style("\n📊 Статистика сессии\n", fg="cyan", bold=True))
    click.echo(f"  Требований:  {click.style(str(total_reqs), fg='green', bold=True)} (завершено: {completed_reqs})")
    click.echo(f"  Тест-кейсов: {click.style(str(total_tests), fg='green', bold=True)}")

    if layer_counts:
        click.echo("\n  По слоям:")
        layer_colors = {'api': 'blue', 'ui': 'yellow', 'e2e': 'magenta', 'integration': 'cyan'}
        for layer, count in sorted(layer_counts.items()):
            color = layer_colors.get(layer, 'white')
            click.echo(f"    {click.style(layer.upper(), fg=color)}: {count}")

    click.echo()


@cli.command("clean")
@click.option("--yes", "-y", is_flag=True, help="Без подтверждения")
def clean(yes: bool):
    """Очищает state и artifacts (с бэкапом)."""
    if not yes and not click.confirm("Очистить state и artifacts (бэкап будет создан)?"):
        return

    cleanup = Cleanup()
    cleanup.prepare_for_new_generation(backup=True)
    click.echo(click.style("✓ Очищено (бэкап создан)", fg="green"))


# =============================================================================
# Raw requirements shortcuts
# =============================================================================

@cli.command("raw")
@click.argument("action", type=click.Choice(["list", "add", "edit", "cat"]), default="list")
@click.argument("name", required=False)
def raw_cmd(action: str, name: str):
    """
    Управление сырыми требованиями в requirements/raw.

    Примеры:
    \b
      python main.py raw list              # список файлов
      python main.py raw cat auth          # показать содержимое auth.md
      python main.py raw add payment       # создать payment.md
      python main.py raw edit auth         # открыть auth.md в редакторе
    """
    raw_dir = Path("requirements/raw")
    raw_dir.mkdir(parents=True, exist_ok=True)

    if action == "list":
        files = sorted(raw_dir.glob("*.md")) + sorted(raw_dir.glob("*.txt"))
        if not files:
            click.echo(click.style("Папка requirements/raw пуста", fg="yellow"))
            click.echo("Создайте файл: python main.py raw add NAME")
            return

        click.echo(click.style("\n📁 requirements/raw:\n", fg="cyan", bold=True))
        for f in files:
            # Считаем требования в файле
            content = f.read_text(encoding="utf-8")
            req_count = content.count("## REQ-") or content.count("# REQ-") or 1
            size_kb = f.stat().st_size / 1024
            click.echo(f"  {click.style(f.name, fg='green')}  ({req_count} req, {size_kb:.1f} KB)")
        click.echo()

    elif action == "cat":
        if not name:
            click.echo(click.style("Укажите имя файла: python main.py raw cat NAME", fg="red"))
            return

        file_path = raw_dir / f"{name}.md"
        if not file_path.exists():
            file_path = raw_dir / name
        if not file_path.exists():
            click.echo(click.style(f"Файл не найден: {name}", fg="red"))
            return

        content = file_path.read_text(encoding="utf-8")
        click.echo(click.style(f"\n--- {file_path.name} ---\n", fg="cyan"))
        click.echo(content)
        click.echo(click.style(f"\n--- end ---\n", fg="cyan"))

    elif action == "add":
        if not name:
            click.echo(click.style("Укажите имя файла: python main.py raw add NAME", fg="red"))
            return

        file_path = raw_dir / f"{name}.md"
        if file_path.exists():
            click.echo(click.style(f"Файл уже существует: {file_path}", fg="yellow"))
            return

        template = f"""# {name.replace('_', ' ').title()} Requirements

## REQ-001 [Back][Front] Название требования

**Описание:**
Описание функциональности.

**Критерии приёмки:**
- [ ] Критерий 1
- [ ] Критерий 2

**API:** `POST /api/v1/{name}`

---

## REQ-002 [Back] Ещё одно требование

**Описание:**
...

"""
        file_path.write_text(template, encoding="utf-8")
        click.echo(click.style(f"✓ Создан: {file_path}", fg="green"))
        click.echo(f"  Редактируйте: python main.py raw edit {name}")

    elif action == "edit":
        if not name:
            click.echo(click.style("Укажите имя файла: python main.py raw edit NAME", fg="red"))
            return

        file_path = raw_dir / f"{name}.md"
        if not file_path.exists():
            file_path = raw_dir / name
        if not file_path.exists():
            click.echo(click.style(f"Файл не найден: {name}", fg="red"))
            return

        import os
        editor = os.environ.get("EDITOR", "nano")
        os.system(f"{editor} {file_path}")


@cli.command("coverage")
def coverage_cmd():
    """Анализирует покрытие требований тестами."""
    sm = StateManager()
    session = sm.load()

    if not session:
        click.echo(click.style("Сессия не найдена. Запустите: python main.py gen", fg="yellow"))
        return

    click.echo(click.style("\n" + "=" * 70, fg="cyan"))
    click.echo(click.style("📊 АНАЛИЗ ПОКРЫТИЯ ТРЕБОВАНИЙ", fg="cyan", bold=True))
    click.echo(click.style("=" * 70, fg="cyan"))

    total_reqs = len(session.requirements)
    total_tests = 0
    layer_counts = {'api': 0, 'ui': 0, 'e2e': 0, 'integration': 0}
    technique_counts = {}

    for req in session.requirements:
        req_tests = len(req.test_cases)
        total_tests += req_tests

        # Извлекаем теги из текста
        text = req.text.lower()
        has_back = '[back]' in text
        has_front = '[front]' in text

        click.echo(f"\n{'─' * 70}")
        status = "✅" if req.status.value == 'completed' else "⏳"
        click.echo(f"{status} {click.style(req.id, fg='green', bold=True)}: {req_tests} тестов")

        # Показываем текст требования (первые 100 символов)
        short_text = req.text[:100].replace('\n', ' ')
        click.echo(click.style(f"   {short_text}...", dim=True))

        # Анализ тегов
        tags_found = []
        if has_back:
            tags_found.append(click.style("[Back]", fg="blue"))
        if has_front:
            tags_found.append(click.style("[Front]", fg="yellow"))
        if tags_found:
            click.echo(f"   Теги: {' '.join(tags_found)}")

        # Подсчёт по слоям и техникам
        test_layers = {}
        test_techniques = {}
        for tc in req.test_cases:
            layer = getattr(tc, 'layer', 'api') or 'api'
            technique = getattr(tc, 'technique', 'unknown') or 'unknown'

            layer_counts[layer] = layer_counts.get(layer, 0) + 1
            test_layers[layer] = test_layers.get(layer, 0) + 1
            test_techniques[technique] = test_techniques.get(technique, 0) + 1
            technique_counts[technique] = technique_counts.get(technique, 0) + 1

        # Показываем распределение по слоям для этого требования
        if test_layers:
            layers_str = ", ".join(f"{k.upper()}={v}" for k, v in sorted(test_layers.items()))
            click.echo(f"   Слои: {layers_str}")

        # Анализ gaps
        gaps = []
        if has_back and test_layers.get('api', 0) == 0:
            gaps.append("❌ Нет API тестов (добавьте endpoint в требование)")
        if has_front and test_layers.get('ui', 0) == 0:
            gaps.append("❌ Нет UI тестов")
        if has_back and has_front and test_layers.get('e2e', 0) == 0:
            gaps.append("⚠️  Нет E2E тестов")

        if gaps:
            click.echo(click.style("   Gaps:", fg="red"))
            for gap in gaps:
                click.echo(f"      {gap}")

    # Итоговая статистика
    click.echo(f"\n{'=' * 70}")
    click.echo(click.style("📈 ИТОГО", fg="cyan", bold=True))
    click.echo(f"{'─' * 70}")
    click.echo(f"   Требований:  {total_reqs}")
    click.echo(f"   Тестов:      {total_tests}")
    click.echo(f"   Среднее:     {total_tests / total_reqs:.1f} тестов/требование" if total_reqs else "")

    click.echo(f"\n   По слоям:")
    layer_colors = {'api': 'blue', 'ui': 'yellow', 'e2e': 'magenta', 'integration': 'cyan'}
    for layer, count in sorted(layer_counts.items()):
        if count > 0:
            color = layer_colors.get(layer, 'white')
            pct = (count / total_tests * 100) if total_tests else 0
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            layer_name = f"{layer.upper():12}"
            click.echo(f"      {click.style(layer_name, fg=color)} {bar} {count:3} ({pct:.0f}%)")

    click.echo(f"\n   По техникам:")
    for technique, count in sorted(technique_counts.items(), key=lambda x: -x[1])[:8]:
        pct = (count / total_tests * 100) if total_tests else 0
        click.echo(f"      {technique:25} {count:3} ({pct:.0f}%)")

    click.echo(click.style("\n" + "=" * 70 + "\n", fg="cyan"))


@cli.command("ls")
def ls_cmd():
    """Показывает список файлов в requirements/raw."""
    raw_dir = Path("requirements/raw")
    if not raw_dir.exists():
        click.echo(click.style("Папка requirements/raw не существует", fg="yellow"))
        return

    files = sorted(raw_dir.glob("*.md")) + sorted(raw_dir.glob("*.txt"))
    if not files:
        click.echo(click.style("Папка пуста", fg="yellow"))
        return

    click.echo(click.style("\n📁 requirements/raw:\n", fg="cyan", bold=True))
    total_reqs = 0
    for f in files:
        content = f.read_text(encoding="utf-8")
        req_count = content.count("## REQ-") or content.count("# REQ-") or 1
        total_reqs += req_count
        click.echo(f"  {click.style(f.name, fg='green', bold=True):30} {req_count:3} req")

    click.echo(click.style(f"\n  Всего: {len(files)} файлов, ~{total_reqs} требований\n", dim=True))


if __name__ == "__main__":
    cli()
