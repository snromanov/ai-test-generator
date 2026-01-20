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
    create_api_crud_test_suite,
    create_state_transition_tests,
    create_performance_tests,
    create_validation_test_cases,
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
    structure_requirements: bool = True  # Нормализовать требования перед генерацией


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
            logger.info("Шаг 1/5: Подготовка проекта...")
            self._prepare()

            # Шаг 2: Загрузка требований
            logger.info("Шаг 2/5: Загрузка требований...")
            req_count, layer_stats, component_stats, skipped = self._load_requirements()

            if req_count == 0:
                return PipelineResult(
                    success=False,
                    error_message="Требования не найдены в источнике"
                )

            # Шаг 3: Структурирование требований
            if self.config.structure_requirements:
                logger.info("Шаг 3/5: Структурирование требований...")
                self._structure_requirements()

            # Шаг 4: Генерация тестов
            logger.info("Шаг 4/5: Генерация тест-кейсов...")
            test_count = self._generate_tests()

            # Шаг 5: Экспорт
            logger.info("Шаг 5/5: Экспорт результатов...")
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

    def _structure_requirements(self) -> int:
        """Нормализует требования и заполняет метаданные для генерации."""
        session = self.sm.load()
        if not session:
            return 0

        parser = StructuredRequirementParser()
        structured_count = 0

        for req in session.requirements:
            parsed = parser.parse(req.text, auto_detect=self.config.auto_detect)
            req.title = parsed.title
            req.layer = parsed.layer.value
            req.component = parsed.component.value
            req.tags = sorted(set(req.tags + parsed.tags))
            req.structured_text = self._build_structured_text(parsed)
            structured_count += 1

        self.sm.save()
        logger.info(f"Структурировано требований: {structured_count}")
        return structured_count

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
            req_obj = self.sm.find_requirement_by_id(req_id)
            
            logger.debug(f"Анализ требования {req_id}...")
            
            # Анализируем требование
            analysis = analyzer.analyze(req_text, req_id)
            self.helper.add_analysis(req_id=req_id, **analyzer.to_helper_format(analysis))

            base_tc_id = f"TC-{req_id.split('-')[1]}"
            text_lower = req_text.lower()
            feedback_hints = self._extract_feedback_hints(req_obj)

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

            # Определяем теги слоёв
            req_tags = getattr(req_obj, 'tags', []) or []
            has_back = any(t.lower() in {'back', 'backend', 'api'} for t in req_tags) or '[back]' in text_lower
            has_front = any(t.lower() in {'front', 'frontend', 'ui'} for t in req_tags) or '[front]' in text_lower

            # API CRUD тесты для [Back] требований
            if has_back and analysis.endpoint:
                req_type = self._infer_crud_type(text_lower)
                if req_type:
                    api_tests = create_api_crud_test_suite(
                        req_id=req_id,
                        base_tc_id=base_tc_id,
                        endpoint=analysis.endpoint,
                        http_method=analysis.http_method or "POST",
                        req_type=req_type,
                        preconditions=['API сервер доступен', 'Пользователь авторизован'],
                        sample_data={'id': 1, 'name': 'TestObject'}
                    )
                    total_added += self.helper.add_test_cases_bulk(req_id, api_tests)

            # State Transition тесты
            if analysis.states and len(analysis.states) > 1:
                valid_transitions = self._infer_valid_transitions(analysis.states)
                invalid_transitions = self._infer_invalid_transitions(analysis.states)
                if valid_transitions or invalid_transitions:
                    st_tests = create_state_transition_tests(
                        req_id=req_id,
                        base_tc_id=base_tc_id,
                        endpoint=analysis.endpoint or "/api/v1/resource/{id}/status",
                        http_method="PUT",
                        valid_transitions=valid_transitions,
                        invalid_transitions=invalid_transitions,
                        preconditions=['API сервер доступен', 'Объект существует']
                    )
                    total_added += self.helper.add_test_cases_bulk(req_id, st_tests)

            # Performance тесты
            if analysis.endpoint and has_back:
                max_response_time = self._extract_response_time(req_text)
                perf_tests = create_performance_tests(
                    req_id=req_id,
                    base_tc_id=base_tc_id,
                    endpoint=analysis.endpoint,
                    http_method=analysis.http_method or "GET",
                    max_response_time_ms=max_response_time,
                    preconditions=['API сервер доступен', 'Система под нормальной нагрузкой']
                )
                total_added += self.helper.add_test_cases_bulk(req_id, perf_tests)

            # E2E тесты для [Back]+[Front]
            if has_back and has_front:
                e2e_tests = self._create_e2e_tests(req_id, base_tc_id, analysis, text_lower)
                total_added += self.helper.add_test_cases_bulk(req_id, e2e_tests)

            # Validation тесты для форм
            if 'ui_form' in analysis.suggested_techniques or has_front:
                field_validations = self._extract_field_validations(req_text, analysis)
                if field_validations:
                    val_tests = create_validation_test_cases(
                        req_id=req_id,
                        base_tc_id=base_tc_id,
                        endpoint=analysis.endpoint or "/api/v1/resource",
                        http_method=analysis.http_method or "POST",
                        fields_validation=field_validations,
                        preconditions=['Форма открыта', 'Пользователь авторизован']
                    )
                    total_added += self.helper.add_test_cases_bulk(req_id, val_tests)

            # Feedback-based heuristics
            if feedback_hints.get("add_integration"):
                integration_test = create_integration_test_case(
                    base_tc_id=f"{base_tc_id}-FB-INT-001",
                    title="Интеграционный сценарий по замечаниям",
                    api_endpoint=analysis.endpoint or None,
                    test_type="Positive",
                    technique="feedback_integration",
                    tags=["feedback", "integration"]
                )
                total_added += self.helper.add_test_cases_bulk(req_id, [integration_test])

            # Отмечаем требование как завершенное
            self.helper.mark_requirement_completed(req_id)

        logger.info(f"Сгенерировано {total_added} тест-кейсов")
        return total_added

    @staticmethod
    def _build_structured_text(parsed) -> str:
        """Собирает нормализованный текст требования из распарсенных данных."""
        lines = [parsed.title]
        if parsed.description:
            lines.append(parsed.description.strip())
        if parsed.sub_requirements:
            lines.append("Sub-requirements:")
            lines.extend(f"- {item}" for item in parsed.sub_requirements)
        if parsed.constraints:
            lines.append("Constraints:")
            lines.extend(f"- {item}" for item in parsed.constraints)
        if parsed.technical_notes:
            lines.append("Technical notes:")
            lines.extend(f"- {item}" for item in parsed.technical_notes)
        if parsed.api_endpoints:
            lines.append("API endpoints:")
            lines.extend(f"- {item}" for item in parsed.api_endpoints)
        if parsed.ui_elements:
            lines.append("UI elements:")
            lines.extend(f"- {item}" for item in parsed.ui_elements)
        return "\n".join(line for line in lines if line)

    @staticmethod
    def _extract_feedback_hints(req_obj) -> dict:
        """Извлекает подсказки для генерации на основе замечаний."""
        if not req_obj:
            return {}
        feedback_text = " ".join(getattr(req_obj, "review_feedback", []) or [])
        if not feedback_text:
            return {}
        text = feedback_text.lower()
        add_integration = any(token in text for token in ["интеграц", "integration", "e2e", "сквозн"])
        if "backend" in text or "бек" in text or "api" in text:
            if getattr(req_obj, "component", None) == "fullstack":
                req_obj.component = "backend"
            req_obj.layer = "api"
        if "frontend" in text or "фронт" in text or "ui" in text:
            if getattr(req_obj, "component", None) == "fullstack":
                req_obj.component = "frontend"
            req_obj.layer = "ui"
        return {"add_integration": add_integration}

    @staticmethod
    def _infer_crud_type(text_lower: str) -> Optional[str]:
        """Определяет тип CRUD операции из текста требования."""
        create_keywords = ['создан', 'create', 'добавл', 'add', 'new', 'регистр', 'register']
        read_keywords = ['получ', 'get', 'read', 'просмотр', 'view', 'показ', 'show', 'отобра', 'display']
        update_keywords = ['обнов', 'update', 'изменен', 'edit', 'редакт', 'modify']
        delete_keywords = ['удал', 'delete', 'remove']
        search_keywords = ['поиск', 'search', 'найти', 'find', 'фильтр', 'filter']

        if any(kw in text_lower for kw in create_keywords):
            return 'create'
        if any(kw in text_lower for kw in update_keywords):
            return 'update'
        if any(kw in text_lower for kw in delete_keywords):
            return 'delete'
        if any(kw in text_lower for kw in search_keywords):
            return 'search'
        if any(kw in text_lower for kw in read_keywords):
            return 'read'
        return None

    @staticmethod
    def _infer_valid_transitions(states: list[str]) -> list[tuple[str, str]]:
        """
        Выводит валидные переходы между состояниями.

        Предполагает линейную последовательность состояний.
        """
        if len(states) < 2:
            return []

        transitions = []
        for i in range(len(states) - 1):
            transitions.append((states[i], states[i + 1]))
        return transitions

    @staticmethod
    def _infer_invalid_transitions(states: list[str]) -> list[tuple[str, str]]:
        """
        Выводит невалидные переходы между состояниями.

        Обратные переходы в линейной последовательности.
        """
        if len(states) < 2:
            return []

        transitions = []
        # Обратные переходы невалидны
        for i in range(len(states) - 1):
            transitions.append((states[i + 1], states[i]))

        # Пропуск состояний невалиден
        if len(states) >= 3:
            transitions.append((states[0], states[-1]))

        return transitions

    def _create_e2e_tests(
        self,
        req_id: str,
        base_tc_id: str,
        analysis,
        text_lower: str
    ) -> list[dict]:
        """Создает E2E тесты для fullstack требований."""
        e2e_tests = []

        # Определяем сценарий на основе анализа
        scenario_name = "полный пользовательский сценарий"
        if "регистр" in text_lower or "register" in text_lower:
            scenario_name = "регистрация пользователя"
        elif "вход" in text_lower or "login" in text_lower:
            scenario_name = "авторизация пользователя"
        elif "создан" in text_lower or "create" in text_lower:
            scenario_name = "создание объекта через UI и проверка в API"
        elif "загрузк" in text_lower or "upload" in text_lower:
            scenario_name = "загрузка файла через UI и проверка сохранения"

        e2e_tests.append({
            'id': f'{base_tc_id}-E2E-001',
            'title': f'E2E: {scenario_name} (happy path)',
            'priority': 'Critical',
            'test_type': 'Positive',
            'technique': 'e2e_testing',
            'preconditions': [
                'Система полностью доступна',
                'Frontend и Backend работают',
                'Тестовые данные подготовлены'
            ],
            'steps': [
                {'step': 1, 'action': 'Открыть страницу в браузере'},
                {'step': 2, 'action': 'Выполнить действия через UI'},
                {'step': 3, 'action': 'Проверить результат в UI'},
                {'step': 4, 'action': f'Проверить данные через API ({analysis.endpoint or "endpoint"})'},
                {'step': 5, 'action': 'Проверить консистентность данных'}
            ],
            'expected_result': '1. UI отображает корректный результат\n2. API возвращает созданные/измененные данные\n3. Данные консистентны между UI и API',
            'layer': 'e2e',
            'component': 'fullstack',
            'tags': ['e2e', 'integration', 'fullstack'],
            'ui_element': None,
            'api_endpoint': analysis.endpoint
        })

        e2e_tests.append({
            'id': f'{base_tc_id}-E2E-002',
            'title': f'E2E: {scenario_name} (error handling)',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'e2e_testing',
            'preconditions': [
                'Система полностью доступна',
                'Frontend и Backend работают'
            ],
            'steps': [
                {'step': 1, 'action': 'Открыть страницу в браузере'},
                {'step': 2, 'action': 'Ввести невалидные данные через UI'},
                {'step': 3, 'action': 'Проверить отображение ошибок в UI'},
                {'step': 4, 'action': 'Проверить что данные НЕ сохранены через API'}
            ],
            'expected_result': '1. UI отображает понятное сообщение об ошибке\n2. API подтверждает отсутствие изменений\n3. Пользователь может исправить данные',
            'layer': 'e2e',
            'component': 'fullstack',
            'tags': ['e2e', 'error-handling', 'fullstack'],
            'ui_element': None,
            'api_endpoint': analysis.endpoint
        })

        return e2e_tests

    @staticmethod
    def _extract_response_time(text: str) -> int:
        """Извлекает максимальное время ответа из текста требования."""
        import re

        # Паттерны для поиска времени ответа
        patterns = [
            r'(\d+)\s*(?:мс|ms|millisecond)',
            r'(\d+)\s*(?:сек|sec|second)',
            r'(?:время ответа|response time)[^\d]*(\d+)',
            r'(\d+)\s*(?:миллисекунд)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                value = int(match.group(1))
                if 'сек' in text.lower() or 'sec' in text.lower():
                    return value * 1000
                return value

        # Значение по умолчанию
        return 2000

    @staticmethod
    def _extract_field_validations(text: str, analysis) -> dict[str, str]:
        """Извлекает правила валидации полей из текста и анализа."""
        validations = {}

        text_lower = text.lower()

        # Ищем упоминания полей и их правил
        field_patterns = {
            'email': 'формат email (обязательное)',
            'телефон': 'формат телефона',
            'phone': 'формат телефона',
            'пароль': 'минимум 8 символов (обязательное)',
            'password': 'минимум 8 символов (обязательное)',
            'имя': 'не пустое (обязательное)',
            'name': 'не пустое (обязательное)',
            'дата': 'корректный формат даты',
            'date': 'корректный формат даты',
            'url': 'валидный URL',
            'сумма': 'положительное число',
            'amount': 'положительное число',
            'возраст': 'целое число от 0 до 150',
            'age': 'целое число от 0 до 150',
        }

        for field, rule in field_patterns.items():
            if field in text_lower:
                validations[field] = rule

        # Добавляем поля из анализа
        if hasattr(analysis, 'inputs') and analysis.inputs:
            for inp in analysis.inputs:
                inp_lower = inp.lower()
                for field, rule in field_patterns.items():
                    if field in inp_lower and field not in validations:
                        validations[field] = rule

        return validations

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
