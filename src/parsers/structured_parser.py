"""
Парсер структурированных требований с тегами [Back], [Front], [API], [UI].

Позволяет работать с различными типами требований:
- Структурированными ([Back]/[Front])
- UI требованиями
- LLM интеграциями
- File upload и др.
"""
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class RequirementLayer(str, Enum):
    """Слой тестирования."""
    API = "api"
    UI = "ui"
    INTEGRATION = "integration"
    E2E = "e2e"


class RequirementComponent(str, Enum):
    """Компонент системы."""
    BACKEND = "backend"
    FRONTEND = "frontend"
    FULLSTACK = "fullstack"


@dataclass
class ParsedRequirement:
    """Распарсенное требование с метаданными."""
    title: str
    description: str
    layer: RequirementLayer = RequirementLayer.API
    component: RequirementComponent = RequirementComponent.FULLSTACK
    tags: list[str] = field(default_factory=list)
    sub_requirements: list[str] = field(default_factory=list)
    technical_notes: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    ui_elements: list[str] = field(default_factory=list)
    api_endpoints: list[str] = field(default_factory=list)
    raw_text: str = ""


class StructuredRequirementParser:
    """
    Парсер для структурированных требований.

    Поддерживает:
    - Теги [Back], [Front], [API], [UI]
    - Нумерованные списки (acceptance criteria)
    - Технические заметки
    - Ограничения
    - Автоопределение слоя и компонента
    """

    # Паттерны для тегов
    TAG_PATTERNS = {
        'back': re.compile(r'\[Back\]', re.IGNORECASE),
        'front': re.compile(r'\[Front\]', re.IGNORECASE),
        'api': re.compile(r'\[API\]', re.IGNORECASE),
        'ui': re.compile(r'\[UI\]', re.IGNORECASE),
        'e2e': re.compile(r'\[E2E\]', re.IGNORECASE),
        'integration': re.compile(r'\[Integration\]', re.IGNORECASE),
    }

    # Ключевые слова для автоопределения слоя
    LAYER_KEYWORDS = {
        RequirementLayer.API: [
            'endpoint', 'api', 'rest', 'graphql', 'http', 'request', 'response',
            'post', 'get', 'put', 'delete', 'patch', 'json', 'запрос', 'ответ',
            'эндпоинт', 'метод'
        ],
        RequirementLayer.UI: [
            'кнопка', 'форма', 'поле', 'ввод', 'экран', 'страница', 'модальное',
            'button', 'form', 'field', 'input', 'screen', 'page', 'modal',
            'dropdown', 'checkbox', 'календарь', 'calendar', 'drag', 'drop',
            'клик', 'click', 'hover', 'scroll'
        ],
        RequirementLayer.INTEGRATION: [
            'интеграция', 'integration', 'webhook', 'callback', 'llm', 'ai',
            'внешний', 'external', 'third-party', 'сторонний'
        ],
        RequirementLayer.E2E: [
            'сценарий', 'scenario', 'end-to-end', 'e2e', 'пользователь',
            'user journey', 'flow', 'путь пользователя'
        ]
    }

    # Ключевые слова для автоопределения компонента
    COMPONENT_KEYWORDS = {
        RequirementComponent.BACKEND: [
            'backend', 'сервер', 'server', 'база данных', 'database', 'db',
            'таблица', 'table', 'миграция', 'migration', 'sql', 'nosql',
            'кэш', 'cache', 'redis', 'queue', 'очередь'
        ],
        RequirementComponent.FRONTEND: [
            'frontend', 'фронтенд', 'ui', 'ux', 'компонент', 'component',
            'react', 'vue', 'angular', 'css', 'стиль', 'style', 'анимация',
            'animation', 'responsive', 'адаптивный'
        ]
    }

    # Паттерны для извлечения данных
    NUMBERED_LIST_PATTERN = re.compile(r'^\s*(\d+)\.\s+(.+)$', re.MULTILINE)
    BULLET_LIST_PATTERN = re.compile(r'^\s*[-•*]\s+(.+)$', re.MULTILINE)
    TECHNICAL_NOTE_PATTERN = re.compile(
        r'(?:Техническая реализация|Technical notes?|Технические заметки?)[:\s]*(.+?)(?=\n\n|\Z)',
        re.IGNORECASE | re.DOTALL
    )
    CONSTRAINT_PATTERN = re.compile(
        r'(?:Максим(?:ум|ально)|Миним(?:ум|ально)|Ограничени[ея]|Constraint|Limit)[:\s]*(.+?)(?=\n|$)',
        re.IGNORECASE
    )
    ENDPOINT_PATTERN = re.compile(
        r'(?:GET|POST|PUT|DELETE|PATCH)\s+(/[\w/{}\-?&=]+)',
        re.IGNORECASE
    )
    UI_ELEMENT_PATTERN = re.compile(
        r'(?:кнопка|button|поле|field|форма|form|модальное окно|modal|dropdown|checkbox|'
        r'календарь|calendar|input|select|textarea)[\s:]+["\']?([^"\'\n,]+)["\']?',
        re.IGNORECASE
    )

    def parse(self, text: str, auto_detect: bool = True) -> ParsedRequirement:
        """
        Парсит текст требования.

        Args:
            text: Текст требования
            auto_detect: Автоматически определять layer/component по ключевым словам

        Returns:
            ParsedRequirement с извлеченными метаданными
        """
        logger.debug(f"Парсинг требования: {text[:100]}...")

        # Извлекаем заголовок (первая строка или до первого тега)
        lines = text.strip().split('\n')
        title = self._extract_title(lines)

        # Извлекаем теги
        tags = self._extract_tags(text)

        # Определяем компонент на основе тегов
        component = self._determine_component(tags, text if auto_detect else "")

        # Определяем слой
        layer = self._determine_layer(tags, text if auto_detect else "")

        # Извлекаем подтребования (нумерованные списки)
        sub_requirements = self._extract_sub_requirements(text)

        # Извлекаем технические заметки
        technical_notes = self._extract_technical_notes(text)

        # Извлекаем ограничения
        constraints = self._extract_constraints(text)

        # Извлекаем UI элементы
        ui_elements = self._extract_ui_elements(text)

        # Извлекаем API эндпоинты
        api_endpoints = self._extract_api_endpoints(text)

        # Формируем описание (текст без заголовка)
        description = self._extract_description(text, title)

        result = ParsedRequirement(
            title=title,
            description=description,
            layer=layer,
            component=component,
            tags=tags,
            sub_requirements=sub_requirements,
            technical_notes=technical_notes,
            constraints=constraints,
            ui_elements=ui_elements,
            api_endpoints=api_endpoints,
            raw_text=text
        )

        logger.info(
            f"Распарсено требование: layer={layer.value}, "
            f"component={component.value}, tags={tags}"
        )

        return result

    def parse_multiple(
        self,
        text: str,
        separator: str = "\n---\n",
        auto_detect: bool = True
    ) -> list[ParsedRequirement]:
        """
        Парсит несколько требований из одного текста.

        Args:
            text: Текст с несколькими требованиями
            separator: Разделитель между требованиями

        Returns:
            Список ParsedRequirement
        """
        # Разделяем по явному разделителю или по заголовкам
        if separator in text:
            blocks = text.split(separator)
        else:
            # Пробуем разделить по markdown заголовкам
            blocks = re.split(r'\n(?=#{1,3}\s+)', text)
            # Если не получилось, пробуем разделение по "сырым" заголовкам
            if len(blocks) == 1:
                blocks = self._split_by_titles(text)
            else:
                expanded = []
                for block in blocks:
                    if self._has_multiple_titles(block):
                        expanded.extend(self._split_by_titles(block))
                    else:
                        expanded.append(block)
                blocks = expanded

        requirements = []
        for block in blocks:
            block = block.strip()
            if block:
                req = self.parse(block, auto_detect=auto_detect)
                requirements.append(req)

        logger.info(f"Распарсено {len(requirements)} требований")
        return requirements

    def _extract_title(self, lines: list[str]) -> str:
        """Извлекает заголовок из строк."""
        for line in lines:
            line = line.strip()
            # Пропускаем пустые строки
            if not line:
                continue
            # Удаляем markdown заголовки
            if line.startswith('#'):
                line = re.sub(r'^#+\s*', '', line)
            # Удаляем теги из заголовка
            for pattern in self.TAG_PATTERNS.values():
                line = pattern.sub('', line)
            line = line.strip()
            if line:
                return line
        return "Untitled Requirement"

    def _extract_tags(self, text: str) -> list[str]:
        """Извлекает все теги из текста."""
        tags = []
        for tag_name, pattern in self.TAG_PATTERNS.items():
            if pattern.search(text):
                tags.append(tag_name)
        return tags

    def _determine_component(self, tags: list[str], text: str) -> RequirementComponent:
        """Определяет компонент на основе тегов и ключевых слов."""
        has_back = 'back' in tags or 'api' in tags
        has_front = 'front' in tags or 'ui' in tags

        if has_back and has_front:
            return RequirementComponent.FULLSTACK
        elif has_back:
            return RequirementComponent.BACKEND
        elif has_front:
            return RequirementComponent.FRONTEND

        # Автоопределение по ключевым словам
        if text:
            text_lower = text.lower()
            backend_score = sum(1 for kw in self.COMPONENT_KEYWORDS[RequirementComponent.BACKEND]
                               if kw in text_lower)
            frontend_score = sum(1 for kw in self.COMPONENT_KEYWORDS[RequirementComponent.FRONTEND]
                                if kw in text_lower)

            if backend_score > 0 and frontend_score > 0:
                return RequirementComponent.FULLSTACK
            elif backend_score > frontend_score:
                return RequirementComponent.BACKEND
            elif frontend_score > backend_score:
                return RequirementComponent.FRONTEND

        return RequirementComponent.FULLSTACK

    def _determine_layer(self, tags: list[str], text: str) -> RequirementLayer:
        """Определяет слой тестирования на основе тегов и ключевых слов."""
        # Явные теги имеют приоритет
        if 'e2e' in tags:
            return RequirementLayer.E2E
        if 'integration' in tags:
            return RequirementLayer.INTEGRATION
        if 'ui' in tags:
            return RequirementLayer.UI
        if 'api' in tags:
            return RequirementLayer.API

        # Автоопределение по ключевым словам
        if text:
            text_lower = text.lower()
            scores = {}
            for layer, keywords in self.LAYER_KEYWORDS.items():
                scores[layer] = sum(1 for kw in keywords if kw in text_lower)

            if scores:
                max_layer = max(scores, key=scores.get)
                if scores[max_layer] > 0:
                    return max_layer

        return RequirementLayer.API

    def _extract_sub_requirements(self, text: str) -> list[str]:
        """Извлекает подтребования из нумерованных и маркированных списков."""
        sub_reqs = []

        # Нумерованные списки
        for match in self.NUMBERED_LIST_PATTERN.finditer(text):
            sub_reqs.append(match.group(2).strip())

        # Маркированные списки
        for match in self.BULLET_LIST_PATTERN.finditer(text):
            item = match.group(1).strip()
            # Пропускаем если это уже есть в нумерованном списке
            if item not in sub_reqs:
                sub_reqs.append(item)

        # Строки с тегами [Back]/[Front]/[API]/[UI]
        tag_line_pattern = re.compile(
            r'^\s*\[(Back|Front|API|UI|E2E|Integration)\]\s+(.+)$',
            re.IGNORECASE | re.MULTILINE
        )
        for match in tag_line_pattern.finditer(text):
            item = match.group(2).strip()
            if item and item not in sub_reqs:
                sub_reqs.append(item)

        return sub_reqs

    def _extract_technical_notes(self, text: str) -> list[str]:
        """Извлекает технические заметки."""
        notes = []
        for match in self.TECHNICAL_NOTE_PATTERN.finditer(text):
            note_text = match.group(1).strip()
            # Разбиваем на отдельные заметки если есть списки
            for line in note_text.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Удаляем маркеры списков
                    line = re.sub(r'^[-•*]\s*', '', line)
                    line = re.sub(r'^\d+\.\s*', '', line)
                    if line:
                        notes.append(line)
        return notes

    def _extract_constraints(self, text: str) -> list[str]:
        """Извлекает ограничения."""
        constraints = []
        for match in self.CONSTRAINT_PATTERN.finditer(text):
            constraint = match.group(0).strip()
            constraints.append(constraint)

        # Также ищем паттерны типа "не более X", "минимум Y"
        additional_patterns = [
            r'не более \d+',
            r'не менее \d+',
            r'максимум \d+',
            r'минимум \d+',
            r'до \d+ (?:символов|файлов|элементов|МБ|KB|GB)',
            r'от \d+ до \d+',
        ]
        for pattern in additional_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                constraint = match.group(0)
                if constraint not in constraints:
                    constraints.append(constraint)

        return constraints

    def _extract_ui_elements(self, text: str) -> list[str]:
        """Извлекает UI элементы."""
        elements = []
        for match in self.UI_ELEMENT_PATTERN.finditer(text):
            element = match.group(1).strip()
            if element and element not in elements:
                elements.append(element)
        return elements

    def _extract_api_endpoints(self, text: str) -> list[str]:
        """Извлекает API эндпоинты."""
        endpoints = []
        for match in self.ENDPOINT_PATTERN.finditer(text):
            endpoint = match.group(0).strip()
            if endpoint not in endpoints:
                endpoints.append(endpoint)
        return endpoints

    def _extract_description(self, text: str, title: str) -> str:
        """Извлекает описание (текст без заголовка)."""
        # Удаляем заголовок из начала
        description = text.strip()

        # Удаляем markdown заголовок
        description = re.sub(r'^#+\s+[^\n]+\n?', '', description)

        # Удаляем заголовок если он есть в начале
        if description.startswith(title):
            description = description[len(title):].strip()

        return description

    def _split_by_titles(self, text: str) -> list[str]:
        """Разбивает текст на блоки по 'сырым' заголовкам."""
        lines = text.splitlines()
        blocks = []
        current = []
        prev_blank = True

        for line in lines:
            if self._is_section_header(line, prev_blank) and current:
                blocks.append("\n".join(current).strip())
                current = []
            current.append(line)
            prev_blank = not line.strip()

        if current:
            blocks.append("\n".join(current).strip())

        return [b for b in blocks if b]

    def _has_multiple_titles(self, text: str) -> bool:
        """Проверяет, есть ли несколько заголовков в блоке."""
        count = 0
        prev_blank = True
        for line in text.splitlines():
            if self._is_section_header(line, prev_blank):
                count += 1
                if count > 1:
                    return True
            prev_blank = not line.strip()
        return False

    def _is_section_header(self, line: str, prev_blank: bool) -> bool:
        """Определяет, выглядит ли строка как заголовок нового блока."""
        if not prev_blank:
            return False
        stripped = line.strip()
        if not stripped:
            return False
        if stripped.startswith("["):
            return False
        if stripped.startswith("#"):
            return True
        if self.NUMBERED_LIST_PATTERN.match(stripped):
            return False
        if self.BULLET_LIST_PATTERN.match(stripped):
            return False
        if re.match(r'^(техническая реализация|технические заметки|technical notes?)\b', stripped, re.IGNORECASE):
            return False
        if stripped.endswith(":") and len(stripped.split()) <= 3:
            return False
        if len(stripped) > 120:
            return False
        return True


def get_layer_display_name(layer: RequirementLayer) -> str:
    """Возвращает отображаемое имя слоя."""
    names = {
        RequirementLayer.API: "API Tests",
        RequirementLayer.UI: "UI Tests",
        RequirementLayer.INTEGRATION: "Integration Tests",
        RequirementLayer.E2E: "E2E Tests",
    }
    return names.get(layer, layer.value)


def get_component_display_name(component: RequirementComponent) -> str:
    """Возвращает отображаемое имя компонента."""
    names = {
        RequirementComponent.BACKEND: "Backend",
        RequirementComponent.FRONTEND: "Frontend",
        RequirementComponent.FULLSTACK: "Fullstack",
    }
    return names.get(component, component.value)
