"""
Pipeline Orchestrator - единая точка входа для генерации тест-кейсов.

Упрощает workflow:
  Источник → Анализ → Генерация → Экспорт

Вместо 4+ команд, пользователь запускает одну:
  python main.py generate --source requirements/raw
"""
from pathlib import Path
import re
from dataclasses import dataclass
from typing import Optional, Literal
from enum import Enum

from src.state.state_manager import StateManager, RequirementStatus
from src.generators.test_case_generator import TestCaseGenerator
from src.parsers.structured_parser import (
    StructuredRequirementParser,
    get_layer_display_name,
)
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
from src.utils.logger import setup_logger
from src.utils.input_validation import validate_file_path, validate_file_size

logger = setup_logger(__name__)


class SourceType(str, Enum):
    """Тип источника требований."""
    RAW = "raw"  # requirements/raw/*.md
    DEMO = "demo"  # demo/*.md
    FILE = "file"  # конкретный файл
    CONFLUENCE = "confluence"  # Confluence API


@dataclass
class PipelineConfig:
    """Конфигурация pipeline."""
    source_type: SourceType
    source_path: Optional[str] = None  # Путь к файлу/директории или PAGE_ID
    output_path: str = "artifacts/test_cases"
    output_format: Literal["excel", "csv", "both"] = "excel"
    agent_type: str = "local_agent"
    auto_detect: bool = True  # Автоопределение layer/component
    backup_artifacts: bool = True
    clean_state: bool = True  # Очистить state перед генерацией
    group_by_layer: bool = True  # Группировать тесты по слоям в экспорте


@dataclass
class PipelineResult:
    """Результат выполнения pipeline."""
    success: bool
    requirements_loaded: int = 0
    tests_generated: int = 0
    export_paths: list[str] = None
    layer_stats: dict = None
    component_stats: dict = None
    skipped_files: int = 0
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.export_paths is None:
            self.export_paths = []
        if self.layer_stats is None:
            self.layer_stats = {}
        if self.component_stats is None:
            self.component_stats = {}


class PipelineOrchestrator:
    """
    Orchestrator для генерации тест-кейсов.
    
    Выполняет полный цикл:
    1. Подготовка (очистка state, бэкап)
    2. Загрузка требований из источника
    3. Анализ и генерация тестов
    4. Экспорт результатов
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.sm: Optional[StateManager] = None
        self.helper: Optional[TestGeneratorHelper] = None

    def run(self) -> PipelineResult:
        """
        Запускает полный pipeline.
        
        Returns:
            PipelineResult с результатами выполнения
        """
        try:
            # Шаг 1: Подготовка
            logger.info("Шаг 1/4: Подготовка проекта...")
            self._prepare()

            # Шаг 2: Загрузка требований
            logger.info("Шаг 2/4: Загрузка требований...")
            req_count, layer_stats, component_stats, skipped = self._load_requirements()

            if req_count == 0:
                return PipelineResult(
                    success=False,
                    error_message="Требования не найдены в источнике"
                )

            # Шаг 3: Генерация тестов
            logger.info("Шаг 3/4: Генерация тест-кейсов...")
            test_count = self._generate_tests()

            # Шаг 4: Экспорт
            logger.info("Шаг 4/4: Экспорт результатов...")
            export_paths = self._export_results()

            return PipelineResult(
                success=True,
                requirements_loaded=req_count,
                tests_generated=test_count,
                export_paths=export_paths,
                layer_stats=layer_stats,
                component_stats=component_stats,
                skipped_files=skipped
            )

        except Exception as e:
            logger.exception("Ошибка выполнения pipeline")
            return PipelineResult(
                success=False,
                error_message=str(e)
            )

    def _prepare(self):
        """Подготовка: очистка state, создание сессии."""
        if self.config.clean_state:
            cleanup = Cleanup()
            cleanup.prepare_for_new_generation(
                backup=self.config.backup_artifacts
            )

        self.sm = StateManager()
        self.sm.create_session(agent_type=self.config.agent_type)
        self.helper = TestGeneratorHelper()

        logger.info("Подготовка завершена")

    def _load_requirements(self) -> tuple[int, dict, dict, int]:
        """
        Загружает требования из источника.
        
        Returns:
            (count, layer_stats, component_stats, skipped_files)
        """
        if self.config.source_type == SourceType.RAW:
            return self._load_from_raw()
        elif self.config.source_type == SourceType.DEMO:
            return self._load_from_demo()
        elif self.config.source_type == SourceType.FILE:
            return self._load_from_file()
        elif self.config.source_type == SourceType.CONFLUENCE:
            return self._load_from_confluence()
        else:
            raise ValueError(f"Неподдерживаемый источник: {self.config.source_type}")

    def _load_from_raw(self) -> tuple[int, dict, dict, int]:
        """Загружает требования из requirements/raw/."""
        dir_path = self.config.source_path or "requirements/raw"
        
        is_valid, error = validate_file_path(dir_path, allow_absolute=True)
        if not is_valid:
            raise ValueError(f"Невалидный путь: {error}")

        root = Path(dir_path)
        if not root.exists() or not root.is_dir():
            raise ValueError(f"Папка не найдена: {dir_path}")

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
                logger.warning(f"Пропущен файл {file_path.name}: {error}")
                skipped_files += 1
                continue

            content = file_path.read_text(encoding="utf-8")
            parsed_requirements = parser.parse_multiple(
                content,
                auto_detect=self.config.auto_detect
            )

            for parsed in parsed_requirements:
                req = self.sm.add_requirement(
                    text=parsed.raw_text or parsed.description,
                    source="file",
                    source_ref=str(file_path)
                )

                # Обновляем расширенные поля
                req_obj = self.sm.find_requirement_by_id(req.id)
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

        self.sm.save()
        logger.info(f"Загружено {total_requirements} требований из {len(files)} файлов")
        return total_requirements, layer_stats, component_stats, skipped_files

    def _load_from_demo(self) -> tuple[int, dict, dict, int]:
        """Загружает демо-требования."""
        demo_dir = Path("demo")
        if not demo_dir.exists():
            raise ValueError("Директория demo не найдена")

        # Определяем файл
        if self.config.source_path:
            demo_file = demo_dir / f"{self.config.source_path}.md"
            if not demo_file.exists():
                demo_file = demo_dir / self.config.source_path
            if not demo_file.exists():
                raise ValueError(f"Демо-файл не найден: {self.config.source_path}")
        else:
            # Берем первый .md файл
            demos = list(demo_dir.glob("*.md"))
            if not demos:
                raise ValueError("Демо-файлы не найдены")
            demo_file = demos[0]

        is_valid, error = validate_file_size(demo_file)
        if not is_valid:
            raise ValueError(f"Невалидный файл: {error}")

        generator = TestCaseGenerator(state_manager=self.sm)
        requirements = generator.load_from_file(str(demo_file))

        if not requirements:
            raise ValueError("Требования не найдены в демо-файле")

        session = self.sm.load()
        layer_stats, component_stats = self._compute_layer_component_stats(session)
        
        logger.info(f"Загружено {len(requirements)} демо-требований")
        return len(requirements), layer_stats, component_stats, 0

    def _load_from_file(self) -> tuple[int, dict, dict, int]:
        """Загружает требования из конкретного файла."""
        if not self.config.source_path:
            raise ValueError("Не указан путь к файлу")

        file_path = Path(self.config.source_path)
        is_valid, error = validate_file_path(str(file_path), allow_absolute=True)
        if not is_valid:
            raise ValueError(f"Невалидный путь: {error}")

        is_valid, error = validate_file_size(file_path)
        if not is_valid:
            raise ValueError(f"Невалидный файл: {error}")

        generator = TestCaseGenerator(state_manager=self.sm)
        requirements = generator.load_from_file(str(file_path))

        if not requirements:
            raise ValueError("Требования не найдены в файле")

        session = self.sm.load()
        layer_stats, component_stats = self._compute_layer_component_stats(session)
        
        logger.info(f"Загружено {len(requirements)} требований из файла")
        return len(requirements), layer_stats, component_stats, 0

    def _load_from_confluence(self) -> tuple[int, dict, dict, int]:
        """Загружает требования из Confluence."""
        if not self.config.source_path:
            raise ValueError("Не указан PAGE_ID для Confluence")

        generator = TestCaseGenerator(state_manager=self.sm)
        requirements = generator.load_from_confluence(self.config.source_path)

        if not requirements:
            raise ValueError("Требования не найдены на странице Confluence")

        session = self.sm.load()
        layer_stats, component_stats = self._compute_layer_component_stats(session)
        
        logger.info(f"Загружено {len(requirements)} требований из Confluence")
        return len(requirements), layer_stats, component_stats, 0

    def _generate_tests(self) -> int:
        """
        Генерирует тест-кейсы для всех требований.
        
        Returns:
            Количество сгенерированных тестов
        """
        analyzer = RequirementAnalyzer()
        total_added = 0

        pending_requirements = self.helper.get_pending_requirements()
        logger.info(f"Обработка {len(pending_requirements)} требований...")

        for req_info in pending_requirements:
            req_id = req_info["id"]
            req_text = self.helper.get_requirement_text(req_id)
            
            logger.debug(f"Анализ требования {req_id}...")
            
            # Анализируем требование
            analysis = analyzer.analyze(req_text, req_id)
            self.helper.add_analysis(req_id=req_id, **analyzer.to_helper_format(analysis))

            base_tc_id = f"TC-{req_id.split('-')[1]}"
            text_lower = req_text.lower()

            # Boundary Value Analysis
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
                    total_added += self.helper.add_test_cases_bulk(req_id, bva_tests)

            # Equivalence Partitioning
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
                    total_added += self.helper.add_test_cases_bulk(req_id, ep_tests)

            # Calendar tests
            if "календар" in text_lower or "calendar" in text_lower:
                calendar_tests = create_calendar_tests(
                    req_id=req_id,
                    base_tc_id=base_tc_id,
                    ui_element="calendar"
                )
                total_added += self.helper.add_test_cases_bulk(req_id, calendar_tests)

            # File upload tests
            if any(token in text_lower for token in ["фото", "файл", "upload", "photo", "file"]):
                max_files = self._extract_max_files(analysis.boundary_values)
                max_size_mb = self._extract_max_size_mb(analysis.boundary_values)
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
                    total_added += self.helper.add_test_cases_bulk(req_id, upload_tests)

            # LLM integration tests
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
                total_added += self.helper.add_test_cases_bulk(req_id, llm_tests)

            # Отмечаем требование как завершенное
            self.helper.mark_requirement_completed(req_id)

        logger.info(f"Сгенерировано {total_added} тест-кейсов")
        return total_added

    def _export_results(self) -> list[str]:
        """
        Экспортирует результаты.
        
        Returns:
            Список путей к экспортированным файлам
        """
        session = self.sm.load()
        if not session or not session.requirements:
            raise ValueError("Нет данных для экспорта")

        # Конвертируем state в GenerationResult
        from src.agents.test_agent import GenerationResult, TestCase, RequirementAnalysis
        
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
                model=self.config.agent_type
            ))

        generator = TestCaseGenerator(state_manager=self.sm)
        export_paths = []

        if self.config.output_format in ("excel", "both"):
            path = generator.export_to_excel(
                results,
                self.config.output_path,
                group_by_layer=self.config.group_by_layer
            )
            export_paths.append(path)
            logger.info(f"Экспорт Excel: {path}")

        if self.config.output_format in ("csv", "both"):
            path = generator.export_to_csv(results, self.config.output_path)
            export_paths.append(path)
            logger.info(f"Экспорт CSV: {path}")

        self.sm.update_progress(step="completed", action=f"exported to {self.config.output_format}")
        return export_paths

    @staticmethod
    def _has_llm_keywords(text_lower: str) -> bool:
        """Проверяет наличие LLM/AI как отдельных токенов, без ложных совпадений."""
        if re.search(r"(?<!\w)(llm|ai)(?!\w)", text_lower):
            return True
        return re.search(r"(?<!\w)ии(?!\w)", text_lower) is not None

    def _extract_max_files(self, boundary_values: dict) -> Optional[int]:
        """Извлекает максимальное количество файлов из boundary_values."""
        for field, bounds in boundary_values.items():
            if bounds.get("type") == "count" and isinstance(bounds.get("max"), int):
                return bounds["max"]
            if field.lower() in {"фото", "photo", "photos", "файлы", "files", "file"}:
                if isinstance(bounds.get("max"), int):
                    return bounds["max"]
        return None

    def _extract_max_size_mb(self, boundary_values: dict) -> Optional[float]:
        """Извлекает максимальный размер файла в МБ из boundary_values."""
        for field, bounds in boundary_values.items():
            if bounds.get("type") == "file_size_mb" and isinstance(bounds.get("max"), (int, float)):
                return bounds["max"]
            if field.lower() in {"file_size", "size", "размер"}:
                if isinstance(bounds.get("max"), (int, float)):
                    return bounds["max"]
        return None

    def _compute_layer_component_stats(self, session) -> tuple[dict, dict]:
        """Вычисляет статистику по слоям и компонентам."""
        layer_stats = {}
        component_stats = {}
        for req in session.requirements:
            layer = getattr(req, "layer", "api") or "api"
            component = getattr(req, "component", "fullstack") or "fullstack"
            layer_stats[layer] = layer_stats.get(layer, 0) + 1
            component_stats[component] = component_stats.get(component, 0) + 1
        return layer_stats, component_stats


def create_orchestrator_from_args(
    source: str,
    output: Optional[str] = None,
    format: str = "excel",
    agent: str = "local_agent",
    no_backup: bool = False,
    no_clean: bool = False,
    no_group: bool = False,
    no_auto_detect: bool = False,
) -> PipelineOrchestrator:
    """
    Создает orchestrator из аргументов CLI.
    
    Args:
        source: Путь к источнику (raw, demo/petstore, file.md, confluence:PAGE_ID)
        output: Путь для экспорта (по умолчанию artifacts/test_cases)
        format: Формат экспорта (excel, csv, both)
        agent: Тип агента
        no_backup: Не делать бэкап artifacts
        no_clean: Не очищать state
        no_group: Не группировать по слоям
        no_auto_detect: Не использовать автоопределение layer/component
    """
    # Определяем тип источника
    if source.startswith("confluence:"):
        source_type = SourceType.CONFLUENCE
        source_path = source.split(":", 1)[1]
    elif source in ("raw", "requirements/raw"):
        source_type = SourceType.RAW
        source_path = "requirements/raw"
    elif source.startswith("demo"):
        source_type = SourceType.DEMO
        if "/" in source:
            source_path = source.split("/", 1)[1].replace(".md", "")
        else:
            source_path = None
    else:
        # Файл
        source_type = SourceType.FILE
        source_path = source

    config = PipelineConfig(
        source_type=source_type,
        source_path=source_path,
        output_path=output or "artifacts/test_cases",
        output_format=format,
        agent_type=agent,
        auto_detect=not no_auto_detect,
        backup_artifacts=not no_backup,
        clean_state=not no_clean,
        group_by_layer=not no_group
    )

    return PipelineOrchestrator(config)
