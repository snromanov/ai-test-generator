"""
State Manager для CLI агентов.

Сохраняет контекст генерации между сессиями для предотвращения
потери контекста и галлюцинаций.
"""
import json
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Literal
from enum import Enum

from src.utils.logger import setup_logger
from src.utils.security import sanitize_requirement, detect_injection
from src.utils.input_validation import (
    validate_requirement_length,
    validate_requirements_count,
    validate_test_cases_count,
)
from src.utils.security_logging import SecurityLogger
from src.utils.state_integrity import (
    sign_state_file,
    verify_signature,
    validate_schema,
    create_backup,
    restore_from_backup,
)
import os

logger = setup_logger(__name__)


class RequirementStatus(str, Enum):
    """Статус обработки требования."""
    PENDING = "pending"           # Ожидает обработки
    ANALYZING = "analyzing"       # Идет анализ
    ANALYZED = "analyzed"         # Проанализировано
    GENERATING = "generating"     # Генерация тестов
    COMPLETED = "completed"       # Тесты сгенерированы
    FAILED = "failed"             # Ошибка обработки
    REVIEW = "review"             # На ревью у пользователя


@dataclass
class TestCaseState:
    """Состояние тест-кейса."""
    id: str
    title: str
    priority: str
    test_type: str
    technique: str
    status: Literal["draft", "approved", "rejected", "modified"] = "draft"
    preconditions: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    expected_result: str = ""
    user_feedback: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    modified_at: Optional[str] = None

    # Новые поля для расширенной классификации (с defaults для обратной совместимости)
    layer: str = "api"  # api | ui | integration | e2e
    component: str = "fullstack"  # backend | frontend | fullstack
    tags: list[str] = field(default_factory=list)
    ui_element: Optional[str] = None  # Для UI тестов
    api_endpoint: Optional[str] = None  # Для API тестов


@dataclass
class RequirementAnalysis:
    """Анализ требования."""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)
    suggested_techniques: list[str] = field(default_factory=list)


@dataclass
class RequirementState:
    """Состояние требования."""
    id: str
    text: str
    source: str  # "file", "confluence", "manual"
    source_ref: Optional[str] = None  # путь к файлу или ID страницы
    status: RequirementStatus = RequirementStatus.PENDING
    analysis: Optional[RequirementAnalysis] = None
    test_cases: list[TestCaseState] = field(default_factory=list)
    hash: str = ""  # для отслеживания изменений
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    processed_at: Optional[str] = None
    error: Optional[str] = None

    # Новые поля для расширенной классификации (с defaults для обратной совместимости)
    layer: str = "api"  # api | ui | integration | e2e
    component: str = "fullstack"  # backend | frontend | fullstack
    tags: list[str] = field(default_factory=list)
    title: Optional[str] = None  # Заголовок требования (из парсера)
    structured_text: Optional[str] = None  # Нормализованный текст для генерации
    review_feedback: list[str] = field(default_factory=list)  # Замечания пользователя

    def __post_init__(self):
        if not self.hash:
            self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Вычисляет хэш текста требования."""
        return hashlib.md5(self.text.encode()).hexdigest()[:12]

    def has_changed(self, new_text: str) -> bool:
        """Проверяет, изменилось ли требование."""
        new_hash = hashlib.md5(new_text.encode()).hexdigest()[:12]
        return new_hash != self.hash


@dataclass
class GenerationProgress:
    """Прогресс генерации."""
    total_requirements: int = 0
    processed_requirements: int = 0
    total_test_cases: int = 0
    approved_test_cases: int = 0
    rejected_test_cases: int = 0
    current_requirement_id: Optional[str] = None
    current_step: Literal[
        "idle",
        "loading",
        "analyzing",
        "selecting_techniques",
        "generating",
        "reviewing",
        "exporting",
        "completed"
    ] = "idle"
    last_action: Optional[str] = None
    last_action_at: Optional[str] = None

    @property
    def completion_percentage(self) -> float:
        if self.total_requirements == 0:
            return 0.0
        return (self.processed_requirements / self.total_requirements) * 100


@dataclass
class SessionState:
    """Состояние сессии генерации."""
    session_id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Конфигурация
    llm_provider: str = "anthropic"
    techniques: list[str] = field(default_factory=list)
    output_format: str = "excel"
    output_path: Optional[str] = None

    # Состояние
    requirements: list[RequirementState] = field(default_factory=list)
    progress: GenerationProgress = field(default_factory=GenerationProgress)

    # Метаданные
    total_tokens_used: int = 0
    agent_type: Optional[str] = None  # "claude_code", "qwen_code", "cursor", etc.
    notes: list[str] = field(default_factory=list)


class StateManager:
    """
    Менеджер состояния для CLI агентов.

    Сохраняет контекст генерации в JSON файл для:
    - Восстановления после перезапуска
    - Продолжения работы с места остановки
    - Предотвращения дублирования
    - Отслеживания изменений
    """

    DEFAULT_STATE_FILE = ".test_generator_state.json"

    def __init__(self, state_file: Optional[str] = None, project_dir: Optional[str] = None):
        """
        Инициализация менеджера состояния.

        Args:
            state_file: Путь к файлу состояния
            project_dir: Директория проекта (для относительных путей)
        """
        self.project_dir = Path(project_dir) if project_dir else Path.cwd()
        self.state_file = Path(state_file) if state_file else self.project_dir / self.DEFAULT_STATE_FILE
        self.state: Optional[SessionState] = None
        os.environ.setdefault(
            "AI_TEST_GEN_SIGNATURE_KEY",
            str(self.project_dir / ".ai-test-gen-signature-key"),
        )

        logger.info(f"StateManager инициализирован: {self.state_file}")

    def create_session(
        self,
        session_id: Optional[str] = None,
        llm_provider: str = "anthropic",
        techniques: Optional[list[str]] = None,
        agent_type: Optional[str] = None
    ) -> SessionState:
        """Создает новую сессию."""
        if session_id is None:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.state = SessionState(
            session_id=session_id,
            llm_provider=llm_provider,
            techniques=techniques or [],
            agent_type=agent_type
        )

        logger.info(f"Создана новая сессия: {session_id}")
        self.save()
        return self.state

    def load(self) -> Optional[SessionState]:
        """Загружает состояние из файла."""
        if not self.state_file.exists():
            logger.debug(f"Файл состояния не найден: {self.state_file}")
            return None

        try:
            needs_resign = False
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate schema before using data
            is_valid_schema, schema_error = validate_schema(data)
            if not is_valid_schema:
                logger.error(f"Невалидная схема state: {schema_error}")
                SecurityLogger.log_state_integrity_failure(str(self.state_file), schema_error)
                return None

            # Verify signature if present
            if "_signature" in data:
                if not verify_signature(data):
                    logger.error("Подпись state невалидна, попытка восстановления из backup")
                    if restore_from_backup(self.state_file):
                        with open(self.state_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        is_valid_schema, schema_error = validate_schema(data)
                        if not is_valid_schema:
                            logger.error(f"Невалидная схема backup state: {schema_error}")
                            SecurityLogger.log_state_integrity_failure(str(self.state_file), schema_error)
                            return None
                        if not verify_signature(data):
                            logger.error("Подпись backup state невалидна")
                            return None
                    else:
                        return None
            else:
                logger.warning("State файл без подписи, будет подписан при следующем сохранении")
                needs_resign = True

            self.state = self._dict_to_session(data)
            if (
                self.state.progress.total_requirements != len(self.state.requirements)
            ):
                logger.warning("Несоответствие total_requirements, пересчёт")
                self.state.progress.total_requirements = len(self.state.requirements)

            if needs_resign:
                self.save()
            logger.info(f"Загружено состояние сессии: {self.state.session_id}")
            return self.state

        except Exception as e:
            logger.error(f"Ошибка загрузки состояния: {e}")
            return None

    def save(self) -> bool:
        """Сохраняет состояние в файл."""
        if not self.state:
            logger.warning("Нет состояния для сохранения")
            return False

        try:
            self.state.updated_at = datetime.now().isoformat()
            data = self._session_to_dict(self.state)
            data = sign_state_file(data)

            if self.state_file.exists():
                create_backup(self.state_file)

            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.state_file.chmod(0o600)

            logger.debug(f"Состояние сохранено: {self.state_file}")
            return True

        except Exception as e:
            logger.error(f"Ошибка сохранения состояния: {e}")
            return False

    def get_or_create_session(self, **kwargs) -> SessionState:
        """Загружает существующую сессию или создает новую."""
        loaded = self.load()
        if loaded:
            return loaded
        return self.create_session(**kwargs)

    # =========================================================================
    # Работа с требованиями
    # =========================================================================

    def add_requirement(
        self,
        text: str,
        source: str = "manual",
        source_ref: Optional[str] = None,
        skip_security: bool = False
    ) -> RequirementState:
        """
        Добавляет требование в сессию.

        Args:
            text: Текст требования
            source: Источник (manual, file, confluence)
            source_ref: Ссылка на источник
            skip_security: Пропустить проверку безопасности
        """
        if not self.state:
            raise ValueError("Сессия не инициализирована")

        is_valid, error = validate_requirement_length(text)
        if not is_valid:
            SecurityLogger.log_validation_failure("requirement_length", text, error)
            raise ValueError(error)

        is_valid, error = validate_requirements_count(len(self.state.requirements) + 1)
        if not is_valid:
            SecurityLogger.log_validation_failure("requirements_count", str(len(self.state.requirements) + 1), error)
            raise ValueError(error)

        # Санитизация и проверка безопасности
        display_text = text
        if not skip_security:
            security_result = sanitize_requirement(text)
            if not security_result.is_safe:
                logger.warning(f"Подозрительное требование (risk={security_result.risk_score}): {text[:50]}...")
                for warning in security_result.warnings:
                    logger.warning(f"Security warning: {warning}")

            # Мы сохраняем санитизированный текст для промпта
            # Но в базе можем хранить и оригинал, если нужно
            display_text = security_result.sanitized

        # Проверяем, нет ли уже такого требования (по оригинальному тексту)
        existing = self.find_requirement_by_text(text)
        if existing:
            logger.info(f"Требование уже существует: {existing.id}")
            return existing

        req_id = f"REQ-{len(self.state.requirements) + 1:03d}"
        requirement = RequirementState(
            id=req_id,
            text=display_text,
            source=source,
            source_ref=source_ref
        )

        self.state.requirements.append(requirement)
        self.state.progress.total_requirements = len(self.state.requirements)
        self.save()

        logger.info(f"Добавлено требование: {req_id}")
        return requirement

    def add_requirements_batch(
        self,
        texts: list[str],
        source: str = "manual",
        source_ref: Optional[str] = None
    ) -> list[RequirementState]:
        """Добавляет несколько требований."""
        requirements = []
        for text in texts:
            req = self.add_requirement(text, source, source_ref)
            requirements.append(req)
        return requirements

    def find_requirement_by_text(self, text: str) -> Optional[RequirementState]:
        """Ищет требование по тексту (хэшу)."""
        if not self.state:
            return None

        target_hash = hashlib.md5(text.encode()).hexdigest()[:12]
        for req in self.state.requirements:
            if req.hash == target_hash:
                return req
        return None

    def find_requirement_by_id(self, req_id: str) -> Optional[RequirementState]:
        """Ищет требование по ID."""
        if not self.state:
            return None

        for req in self.state.requirements:
            if req.id == req_id:
                return req
        return None

    def update_requirement_status(
        self,
        req_id: str,
        status: RequirementStatus,
        error: Optional[str] = None
    ):
        """Обновляет статус требования."""
        req = self.find_requirement_by_id(req_id)
        if req:
            req.status = status
            if status == RequirementStatus.COMPLETED:
                req.processed_at = datetime.now().isoformat()
            if error:
                req.error = error
            self.save()

    def set_requirement_analysis(
        self,
        req_id: str,
        inputs: list[str],
        outputs: list[str],
        business_rules: list[str],
        states: list[str],
        suggested_techniques: Optional[list[str]] = None
    ):
        """Сохраняет анализ требования."""
        req = self.find_requirement_by_id(req_id)
        if req:
            req.analysis = RequirementAnalysis(
                inputs=inputs,
                outputs=outputs,
                business_rules=business_rules,
                states=states,
                suggested_techniques=suggested_techniques or []
            )
            req.status = RequirementStatus.ANALYZED
            self.save()

    def add_requirement_feedback(self, req_id: str, feedback: str):
        """Сохраняет замечание пользователя по требованию."""
        req = self.find_requirement_by_id(req_id)
        if not req:
            return
        note = (feedback or "").strip()
        if not note:
            return
        req.review_feedback.append(note)
        self.save()

    def get_requirement_feedback(self, req_id: str) -> list[str]:
        """Возвращает список замечаний пользователя по требованию."""
        req = self.find_requirement_by_id(req_id)
        if not req:
            return []
        return list(req.review_feedback)

    # =========================================================================
    # Работа с тест-кейсами
    # =========================================================================

    def add_test_case(
        self,
        req_id: str,
        test_case: TestCaseState
    ) -> TestCaseState:
        """Добавляет тест-кейс к требованию."""
        req = self.find_requirement_by_id(req_id)
        if not req:
            raise ValueError(f"Требование не найдено: {req_id}")

        is_valid, error = validate_test_cases_count(len(req.test_cases) + 1)
        if not is_valid:
            SecurityLogger.log_validation_failure("test_cases_count", str(len(req.test_cases) + 1), error)
            raise ValueError(error)

        # Проверяем уникальность ID
        existing_ids = {tc.id for tc in req.test_cases}
        if test_case.id in existing_ids:
            # Генерируем новый ID
            base_id = test_case.id.rsplit("-", 1)[0]
            counter = len(req.test_cases) + 1
            test_case.id = f"{base_id}-{counter:03d}"

        req.test_cases.append(test_case)
        self.state.progress.total_test_cases += 1
        self.save()

        logger.info(f"Добавлен тест-кейс: {test_case.id} для {req_id}")
        return test_case

    def update_test_case_status(
        self,
        req_id: str,
        test_case_id: str,
        status: Literal["draft", "approved", "rejected", "modified"],
        feedback: Optional[str] = None
    ):
        """Обновляет статус тест-кейса."""
        req = self.find_requirement_by_id(req_id)
        if not req:
            return

        for tc in req.test_cases:
            if tc.id == test_case_id:
                tc.status = status
                tc.modified_at = datetime.now().isoformat()
                if feedback:
                    tc.user_feedback = feedback

                # Обновляем счетчики
                if status == "approved":
                    self.state.progress.approved_test_cases += 1
                elif status == "rejected":
                    self.state.progress.rejected_test_cases += 1

                self.save()
                break

    def bulk_approve_test_cases(self, req_id: str, test_case_ids: list[str]):
        """Массово одобряет тест-кейсы."""
        for tc_id in test_case_ids:
            self.update_test_case_status(req_id, tc_id, "approved")

    # =========================================================================
    # Работа с прогрессом
    # =========================================================================

    def update_progress(
        self,
        step: Optional[str] = None,
        current_requirement_id: Optional[str] = None,
        action: Optional[str] = None
    ):
        """Обновляет прогресс."""
        if not self.state:
            return

        if step:
            self.state.progress.current_step = step
        if current_requirement_id:
            self.state.progress.current_requirement_id = current_requirement_id
        if action:
            self.state.progress.last_action = action
            self.state.progress.last_action_at = datetime.now().isoformat()

        # Пересчитываем прогресс
        completed = sum(1 for r in self.state.requirements if r.status == RequirementStatus.COMPLETED)
        self.state.progress.processed_requirements = completed

        self.save()

    def add_note(self, note: str):
        """Добавляет заметку к сессии."""
        if self.state:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.state.notes.append(f"[{timestamp}] {note}")
            self.save()

    # =========================================================================
    # Получение состояния
    # =========================================================================

    def get_pending_requirements(self) -> list[RequirementState]:
        """Возвращает необработанные требования."""
        if not self.state:
            return []
        return [r for r in self.state.requirements if r.status == RequirementStatus.PENDING]

    def get_summary(self) -> dict:
        """Возвращает сводку по текущей сессии."""
        if not self.state:
            return {"error": "Сессия не инициализирована"}

        return {
            "session_id": self.state.session_id,
            "created_at": self.state.created_at,
            "updated_at": self.state.updated_at,
            "llm_provider": self.state.llm_provider,
            "agent_type": self.state.agent_type,
            "progress": {
                "total_requirements": self.state.progress.total_requirements,
                "processed": self.state.progress.processed_requirements,
                "completion": f"{self.state.progress.completion_percentage:.1f}%",
                "current_step": self.state.progress.current_step,
                "total_test_cases": self.state.progress.total_test_cases,
                "approved": self.state.progress.approved_test_cases,
                "rejected": self.state.progress.rejected_test_cases,
            },
            "requirements": [
                {
                    "id": r.id,
                    "status": r.status.value,
                    "test_cases_count": len(r.test_cases),
                    "text_preview": r.text[:50] + "..." if len(r.text) > 50 else r.text
                }
                for r in self.state.requirements
            ],
            "tokens_used": self.state.total_tokens_used,
            "notes_count": len(self.state.notes)
        }

    def get_context_for_agent(self) -> str:
        """
        Возвращает контекст для CLI агента в текстовом формате.

        Это основной метод для предотвращения потери контекста -
        агент может использовать его для восстановления состояния.
        """
        if not self.state:
            return "Сессия не инициализирована. Создайте новую сессию."

        lines = [
            "=" * 60,
            "ТЕКУЩЕЕ СОСТОЯНИЕ ГЕНЕРАЦИИ ТЕСТОВ",
            "=" * 60,
            "",
            f"Сессия: {self.state.session_id}",
            f"Обновлено: {self.state.updated_at}",
            f"Провайдер: {self.state.llm_provider}",
            f"Агент: {self.state.agent_type or 'не указан'}",
            "",
            "--- ПРОГРЕСС ---",
            f"Шаг: {self.state.progress.current_step}",
            f"Требований: {self.state.progress.processed_requirements}/{self.state.progress.total_requirements}",
            f"Тест-кейсов: {self.state.progress.total_test_cases}",
            f"  - одобрено: {self.state.progress.approved_test_cases}",
            f"  - отклонено: {self.state.progress.rejected_test_cases}",
            "",
            "--- ТРЕБОВАНИЯ ---"
        ]

        for req in self.state.requirements:
            status_icon = {
                RequirementStatus.PENDING: "⏳",
                RequirementStatus.ANALYZING: "🔍",
                RequirementStatus.ANALYZED: "📋",
                RequirementStatus.GENERATING: "⚙️",
                RequirementStatus.COMPLETED: "✅",
                RequirementStatus.FAILED: "❌",
                RequirementStatus.REVIEW: "👀"
            }.get(req.status, "?")

            lines.append(f"\n{status_icon} {req.id}: {req.status.value}")
            lines.append(f"   Текст: {req.text[:80]}{'...' if len(req.text) > 80 else ''}")
            lines.append(f"   Тесты: {len(req.test_cases)}")

            if req.analysis:
                lines.append(f"   Входы: {len(req.analysis.inputs)}, Выходы: {len(req.analysis.outputs)}")

        if self.state.notes:
            lines.append("\n--- ЗАМЕТКИ ---")
            for note in self.state.notes[-5:]:  # Последние 5 заметок
                lines.append(note)

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def clear(self):
        """Очищает состояние и удаляет файл."""
        if self.state_file.exists():
            self.state_file.unlink()
        self.state = None
        logger.info("Состояние очищено")

    # =========================================================================
    # Приватные методы сериализации
    # =========================================================================

    def _session_to_dict(self, session: SessionState) -> dict:
        """Конвертирует сессию в словарь для JSON."""
        def convert(obj):
            if hasattr(obj, "__dict__"):
                result = {}
                for key, value in obj.__dict__.items():
                    if isinstance(value, Enum):
                        result[key] = value.value
                    elif isinstance(value, list):
                        result[key] = [convert(item) for item in value]
                    elif hasattr(value, "__dict__"):
                        result[key] = convert(value)
                    else:
                        result[key] = value
                return result
            return obj

        return convert(session)

    def _dict_to_session(self, data: dict) -> SessionState:
        """Конвертирует словарь в сессию."""
        # Восстанавливаем требования
        requirements = []
        for req_data in data.get("requirements", []):
            # Анализ
            analysis = None
            if req_data.get("analysis"):
                analysis = RequirementAnalysis(**req_data["analysis"])

            # Тест-кейсы
            test_cases = []
            for tc_data in req_data.get("test_cases", []):
                # Добавляем defaults для новых полей при десериализации старых данных
                tc_data.setdefault("layer", "api")
                tc_data.setdefault("component", "fullstack")
                tc_data.setdefault("tags", [])
                tc_data.setdefault("ui_element", None)
                tc_data.setdefault("api_endpoint", None)
                test_cases.append(TestCaseState(**tc_data))

            req = RequirementState(
                id=req_data["id"],
                text=req_data["text"],
                source=req_data["source"],
                source_ref=req_data.get("source_ref"),
                status=RequirementStatus(req_data.get("status", "pending")),
                analysis=analysis,
                test_cases=test_cases,
                hash=req_data.get("hash", ""),
                created_at=req_data.get("created_at", ""),
                processed_at=req_data.get("processed_at"),
                error=req_data.get("error"),
                # Новые поля с defaults для обратной совместимости
                layer=req_data.get("layer", "api"),
                component=req_data.get("component", "fullstack"),
                tags=req_data.get("tags", []),
                title=req_data.get("title")
            )
            requirements.append(req)

        # Прогресс
        progress_data = data.get("progress", {})
        progress = GenerationProgress(
            total_requirements=progress_data.get("total_requirements", 0),
            processed_requirements=progress_data.get("processed_requirements", 0),
            total_test_cases=progress_data.get("total_test_cases", 0),
            approved_test_cases=progress_data.get("approved_test_cases", 0),
            rejected_test_cases=progress_data.get("rejected_test_cases", 0),
            current_requirement_id=progress_data.get("current_requirement_id"),
            current_step=progress_data.get("current_step", "idle"),
            last_action=progress_data.get("last_action"),
            last_action_at=progress_data.get("last_action_at")
        )

        return SessionState(
            session_id=data["session_id"],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            llm_provider=data.get("llm_provider", "anthropic"),
            techniques=data.get("techniques", []),
            output_format=data.get("output_format", "excel"),
            output_path=data.get("output_path"),
            requirements=requirements,
            progress=progress,
            total_tokens_used=data.get("total_tokens_used", 0),
            agent_type=data.get("agent_type"),
            notes=data.get("notes", [])
        )
