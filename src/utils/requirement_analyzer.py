"""
Автоматический анализатор требований для генерации тест-кейсов.

Извлекает из текста требования:
- HTTP методы и endpoints
- Входные и выходные параметры
- Бизнес-правила и валидации
- Граничные значения
- Состояния объектов
- Рекомендуемые техники тест-дизайна
"""
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class RequirementAnalysis:
    """Результат анализа требования."""
    endpoint: str
    http_method: str
    inputs: List[str]
    outputs: List[str]
    business_rules: List[str]
    states: List[str]
    boundary_values: Dict[str, Dict[str, Any]]
    equivalence_classes: Dict[str, Dict[str, List[str]]]
    suggested_techniques: List[str]
    requirement_type: str  # 'create', 'read', 'update', 'delete', 'search', 'other'


class RequirementAnalyzer:
    """
    Автоматический анализатор требований.
    
    Извлекает структурированную информацию из текста требования
    для автоматической генерации тест-кейсов.
    """
    
    # HTTP методы
    HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
    
    # Паттерны для извлечения
    ENDPOINT_PATTERN = r'(GET|POST|PUT|DELETE|PATCH)\s+(/[\w/{}\-]+)'
    STATUS_CODE_PATTERN = r'(\d{3})\s+([\w\s]+)'
    FIELD_PATTERN = r'(\w+)\s*\(([^)]+)\)'
    RANGE_PATTERN = r'(\d+)\s*(?:до|to|-)\s*(\d+)'
    LENGTH_PATTERN = r'(?:длина|length|от)\s*(\d+)\s*(?:до|to|-|символов)\s*(\d+)'
    ENUM_PATTERN = r'(?:значения|values|допустимые):\s*([^\n.]+)'
    
    def __init__(self):
        pass
    
    def analyze(self, req_text: str, req_id: str = None) -> RequirementAnalysis:
        """
        Анализирует текст требования и извлекает структурированную информацию.
        
        Args:
            req_text: Текст требования
            req_id: ID требования (опционально)
        
        Returns:
            RequirementAnalysis с извлеченной информацией
        """
        logger.info(f"Начало анализа требования {req_id or 'unknown'}")
        
        # Определить endpoint и HTTP метод
        endpoint, http_method = self._extract_endpoint(req_text)
        
        # Определить тип требования
        req_type = self._determine_requirement_type(http_method, req_text)
        
        # Извлечь входные параметры
        inputs = self._extract_inputs(req_text)
        
        # Извлечь выходные параметры (коды ответов)
        outputs = self._extract_outputs(req_text)
        
        # Извлечь бизнес-правила
        business_rules = self._extract_business_rules(req_text)
        
        # Извлечь состояния
        states = self._extract_states(req_text)
        
        # Извлечь граничные значения
        boundary_values = self._extract_boundary_values(req_text, inputs)
        
        # Извлечь классы эквивалентности
        equivalence_classes = self._extract_equivalence_classes(req_text, inputs, states)
        
        # Предложить техники тест-дизайна
        techniques = self._suggest_techniques(
            req_type, boundary_values, equivalence_classes, states
        )
        
        result = RequirementAnalysis(
            endpoint=endpoint,
            http_method=http_method,
            inputs=inputs,
            outputs=outputs,
            business_rules=business_rules,
            states=states,
            boundary_values=boundary_values,
            equivalence_classes=equivalence_classes,
            suggested_techniques=techniques,
            requirement_type=req_type
        )
        
        logger.info(f"Анализ завершен: {len(inputs)} входов, {len(outputs)} выходов, "
                   f"{len(techniques)} техник")
        
        return result
    
    def _extract_endpoint(self, text: str) -> Tuple[str, str]:
        """Извлекает endpoint и HTTP метод."""
        match = re.search(self.ENDPOINT_PATTERN, text, re.IGNORECASE)
        if match:
            method = match.group(1).upper()
            endpoint = match.group(2)
            return endpoint, method
        return '', ''
    
    def _determine_requirement_type(self, http_method: str, text: str) -> str:
        """Определяет тип требования на основе HTTP метода и текста."""
        text_lower = text.lower()
        
        if http_method == 'POST':
            if 'создан' in text_lower or 'добавл' in text_lower or 'новый' in text_lower:
                return 'create'
        elif http_method == 'GET':
            if 'поиск' in text_lower or 'найти' in text_lower or 'findby' in text_lower:
                return 'search'
            return 'read'
        elif http_method == 'PUT':
            return 'update'
        elif http_method == 'DELETE':
            return 'delete'
        
        return 'other'
    
    def _extract_inputs(self, text: str) -> List[str]:
        """Извлекает входные параметры."""
        inputs = []
        
        # Поиск параметров в формате: name (type)
        matches = re.finditer(self.FIELD_PATTERN, text)
        for match in matches:
            field_name = match.group(1)
            if field_name not in ['integer', 'string', 'object', 'array', 'boolean']:
                inputs.append(field_name)
        
        # Поиск параметров в пути URL
        path_params = re.findall(r'\{(\w+)\}', text)
        inputs.extend(path_params)
        
        # Удаление дубликатов
        return list(set(inputs))
    
    def _extract_outputs(self, text: str) -> List[str]:
        """Извлекает коды ответов и статусы."""
        outputs = []
        
        # Поиск HTTP статус кодов
        matches = re.finditer(self.STATUS_CODE_PATTERN, text)
        for match in matches:
            code = match.group(1)
            status = match.group(2).strip()
            outputs.append(f"{code} {status}")
        
        return outputs
    
    def _extract_business_rules(self, text: str) -> List[str]:
        """Извлекает бизнес-правила и валидации."""
        rules = []
        
        # Поиск секций с правилами
        rule_keywords = [
            'бизнес-правил', 'валидаци', 'ограничени', 'требовани',
            'business rule', 'validation', 'constraint'
        ]
        
        sentences = re.split(r'[.;]', text)
        for sentence in sentences:
            sentence = sentence.strip()
            if any(keyword in sentence.lower() for keyword in rule_keywords):
                if sentence and len(sentence) > 10:
                    rules.append(sentence)
        
        # Поиск паттернов валидации
        # Пример: "id должен быть больше нуля"
        validation_patterns = [
            r'(\w+)\s+должен\s+быть\s+([^.,;]+)',
            r'(\w+)\s+не\s+может\s+([^.,;]+)',
            r'если\s+([^.,;]+),\s+(?:то\s+)?([^.,;]+)',
        ]
        
        for pattern in validation_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                rule = match.group(0).strip()
                if rule not in rules:
                    rules.append(rule)
        
        return rules[:10]  # Ограничим количество
    
    def _extract_states(self, text: str) -> List[str]:
        """Извлекает возможные состояния объектов."""
        states = []
        
        # Поиск перечислений состояний
        state_keywords = ['статус', 'status', 'состояни', 'state']
        
        for keyword in state_keywords:
            # Ищем паттерн: "status: value1, value2, value3"
            pattern = rf'{keyword}[:\s]+([^\n.]+)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                values_text = match.group(1)
                # Разбить по запятым или |
                values = re.split(r'[,|]', values_text)
                for val in values:
                    val = val.strip()
                    # Удалить кавычки и лишние символы
                    val = re.sub(r'["\']', '', val)
                    if val and len(val) < 30 and val.isalnum() or '-' in val or '_' in val:
                        states.append(val)
        
        return list(set(states))
    
    def _extract_boundary_values(self, text: str, inputs: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Извлекает граничные значения для полей.
        
        Returns:
            Dict вида: {'field_name': {'min': 1, 'max': 100, 'type': 'integer'}}
        """
        boundary_values = {}
        
        # Поиск диапазонов для каждого поля
        for field in inputs:
            # Поиск паттерна: "field: от X до Y"
            pattern = rf'{field}[:\s]+(?:от\s+)?(\d+)\s+(?:до|to|-)\s+(\d+)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                boundary_values[field] = {
                    'min': int(match.group(1)),
                    'max': int(match.group(2)),
                    'type': 'integer'
                }
                continue
            
            # Поиск длины строки: "длиной от X до Y"
            pattern = rf'{field}.*?(?:длина|length).*?(\d+).*?(\d+)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                boundary_values[field] = {
                    'min': int(match.group(1)),
                    'max': int(match.group(2)),
                    'type': 'string_length'
                }
        
        # Общие диапазоны в тексте
        range_matches = re.finditer(self.RANGE_PATTERN, text)
        for match in range_matches:
            min_val = int(match.group(1))
            max_val = int(match.group(2))
            # Попытаться определить к какому полю относится
            context = text[max(0, match.start()-50):match.start()]
            for field in inputs:
                if field.lower() in context.lower():
                    if field not in boundary_values:
                        boundary_values[field] = {
                            'min': min_val,
                            'max': max_val,
                            'type': 'integer'
                        }
                    break
        
        return boundary_values
    
    def _extract_equivalence_classes(
        self, 
        text: str, 
        inputs: List[str],
        states: List[str]
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        Извлекает классы эквивалентности для полей.
        
        Returns:
            Dict вида: {'field_name': {'valid': [...], 'invalid': [...]}}
        """
        eq_classes = {}
        
        # Если есть states, они являются классами для поля status
        if states:
            eq_classes['status'] = {
                'valid': states,
                'invalid': ['unknown', 'invalid', 'deleted', '']
            }
        
        # Поиск перечислений для других полей
        for field in inputs:
            if field in eq_classes:
                continue
            
            # Поиск допустимых значений
            pattern = rf'{field}.*?(?:допустимые значения|values):\s*([^\n.]+)'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                values_text = match.group(1)
                values = re.split(r'[,|]', values_text)
                valid_values = [v.strip() for v in values if v.strip()]
                
                eq_classes[field] = {
                    'valid': valid_values,
                    'invalid': ['invalid', 'unknown', '']
                }
        
        return eq_classes
    
    def _suggest_techniques(
        self,
        req_type: str,
        boundary_values: Dict[str, Any],
        equivalence_classes: Dict[str, Any],
        states: List[str]
    ) -> List[str]:
        """Предлагает оптимальные техники тест-дизайна."""
        techniques = []
        
        # Граничные значения
        if boundary_values:
            techniques.append('boundary_value')
        
        # Классы эквивалентности
        if equivalence_classes:
            techniques.append('equivalence_partitioning')
        
        # Переходы состояний
        if states and len(states) > 1:
            techniques.append('state_transition')
        
        # В зависимости от типа требования
        if req_type == 'create':
            techniques.append('error_guessing')  # Дубликаты, конфликты
        elif req_type == 'delete':
            techniques.append('error_guessing')  # Удаление несуществующего
        elif req_type == 'search':
            techniques.append('decision_table')  # Комбинации параметров
        
        # Всегда добавляем базовые техники
        if not techniques:
            techniques = ['equivalence_partitioning', 'error_guessing']
        
        return list(set(techniques))
    
    def to_helper_format(self, analysis: RequirementAnalysis) -> Dict[str, Any]:
        """
        Преобразует анализ в формат для TestGeneratorHelper.add_analysis().
        
        Returns:
            Словарь с параметрами для add_analysis()
        """
        return {
            'inputs': analysis.inputs,
            'outputs': analysis.outputs,
            'business_rules': analysis.business_rules,
            'states': analysis.states,
            'suggested_techniques': analysis.suggested_techniques
        }
