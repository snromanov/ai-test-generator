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
from src.state.state_manager import StateManager
from src.utils.project_info import ProjectInfo
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


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
    demo_dir = Path("demo")
    if not demo_dir.exists():
        click.echo(click.style("Директория demo не найдена", fg="red"))
        return

    demos = list(demo_dir.glob("*.md"))
    if not demos:
        click.echo(click.style("Демо-файлы не найдены", fg="yellow"))
        return

    if not name:
        click.echo("\nДоступные демо-требования:")
        for i, demo in enumerate(demos, 1):
            click.echo(f"  {i}. {demo.stem}")
        
        choice = click.prompt("\nВыберите номер или введите имя", type=str)
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(demos):
                selected = demos[idx]
            else:
                click.echo("Неверный номер")
                return
        except ValueError:
            selected = demo_dir / f"{choice}.md"
            if not selected.exists():
                click.echo(f"Файл {selected} не найден")
                return
    else:
        selected = demo_dir / f"{name}.md"
        if not selected.exists():
            # Попробуем найти без расширения
            selected = demo_dir / name
            if not selected.exists():
                click.echo(f"Демо {name} не найдено")
                return

    click.echo(f"Загрузка демо-требований: {selected.name}")
    
    try:
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


# =============================================================================
# Информационные команды
# =============================================================================

@cli.command()
def techniques():
    """Показывает доступные техники тест-дизайна."""
    click.echo("\nДоступные техники тест-дизайна:\n")

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
@click.option("--agent", "-a", type=str, help="Тип CLI агента (claude_code, qwen_code, cursor)")
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
            click.echo("  python main.py state export -f excel")


@state.command("export")
@click.option("--output", "-o", default="test_cases", help="Имя выходного файла")
@click.option("--format", "-f", type=click.Choice(["excel", "csv", "both"]), default="excel")
def state_export(output: str, format: str):
    """Экспортирует результаты из state."""
    sm = StateManager()
    session = sm.load()

    if not session:
        click.echo(click.style("Сессия не найдена.", fg="red"))
        return

    if not session.requirements:
        click.echo(click.style("Нет требований для экспорта.", fg="yellow"))
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
                technique=tc.technique
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
        path = generator.export_to_excel(results, output)
        click.echo(f"Excel: {click.style(path, fg='green')}")

    if format in ("csv", "both"):
        path = generator.export_to_csv(results, output)
        click.echo(f"CSV: {click.style(path, fg='green')}")

    sm.update_progress(step="completed", action=f"exported to {format}")


if __name__ == "__main__":
    cli()
