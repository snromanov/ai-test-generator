"""
Вспомогательный модуль для автоматической генерации тест-кейсов.

Используется CLI агентами для упрощения процесса создания тестов.
"""
from typing import List, Dict, Any, Tuple
from src.state.state_manager import StateManager, TestCaseState
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class TestGeneratorHelper:
    """
    Помощник для генерации тест-кейсов.
    
    Упрощает создание тестов, автоматизируя рутинные операции.
    """
    
    def __init__(self):
        self.sm = StateManager()
        self.current_req_id = None
        
    def set_current_requirement(self, req_id: str):
        """Устанавливает текущее требование для работы."""
        self.current_req_id = req_id
        req = self.sm.find_requirement_by_id(req_id)
        if not req:
            raise ValueError(f"Требование {req_id} не найдено")
        logger.info(f"Текущее требование: {req_id}")
    
    def add_analysis(
        self,
        req_id: str,
        inputs: List[str],
        outputs: List[str],
        business_rules: List[str],
        states: List[str] = None,
        suggested_techniques: List[str] = None
    ):
        """
        Добавляет анализ требования.
        
        Args:
            req_id: ID требования
            inputs: Входные данные
            outputs: Выходные данные (коды ответов, сообщения)
            business_rules: Бизнес-правила и валидации
            states: Возможные состояния (если применимо)
            suggested_techniques: Рекомендуемые техники тест-дизайна
        """
        self.sm.set_requirement_analysis(
            req_id=req_id,
            inputs=inputs,
            outputs=outputs,
            business_rules=business_rules,
            states=states or [],
            suggested_techniques=suggested_techniques or []
        )
        logger.info(f"Анализ добавлен для {req_id}")
    
    def add_test_case(
        self,
        req_id: str,
        tc_id: str,
        title: str,
        priority: str,
        test_type: str,
        technique: str,
        preconditions: List[str],
        steps: List[Dict[str, Any]],
        expected_result: str
    ) -> TestCaseState:
        """
        Добавляет тест-кейс к требованию.
        
        Args:
            req_id: ID требования
            tc_id: ID тест-кейса (например, TC-003-001)
            title: Название теста
            priority: High, Medium, Low
            test_type: Positive, Negative, Boundary, Performance
            technique: Техника тест-дизайна
            preconditions: Список предусловий
            steps: Список шагов [{"step": 1, "action": "..."}]
            expected_result: Ожидаемый результат
        
        Returns:
            Созданный тест-кейс
        """
        tc = TestCaseState(
            id=tc_id,
            title=title,
            priority=priority,
            test_type=test_type,
            technique=technique,
            preconditions=preconditions,
            steps=steps,
            expected_result=expected_result
        )
        
        return self.sm.add_test_case(req_id, tc)
    
    def add_test_cases_bulk(
        self,
        req_id: str,
        test_cases: List[Dict[str, Any]]
    ) -> int:
        """
        Массово добавляет тест-кейсы к требованию.
        
        Args:
            req_id: ID требования
            test_cases: Список тест-кейсов в виде словарей
        
        Returns:
            Количество добавленных тест-кейсов
        
        Example:
            test_cases = [
                {
                    'id': 'TC-003-001',
                    'title': 'Успешное создание',
                    'priority': 'High',
                    'test_type': 'Positive',
                    'technique': 'equivalence_partitioning',
                    'preconditions': ['API доступен'],
                    'steps': [{'step': 1, 'action': 'Отправить POST'}],
                    'expected_result': '201 Created'
                }
            ]
        """
        count = 0
        for tc_data in test_cases:
            self.add_test_case(
                req_id=req_id,
                tc_id=tc_data['id'],
                title=tc_data['title'],
                priority=tc_data['priority'],
                test_type=tc_data['test_type'],
                technique=tc_data['technique'],
                preconditions=tc_data['preconditions'],
                steps=tc_data['steps'],
                expected_result=tc_data['expected_result']
            )
            count += 1
        
        logger.info(f"Добавлено {count} тест-кейсов для {req_id}")
        return count
    
    def mark_requirement_completed(self, req_id: str):
        """Отмечает требование как обработанное."""
        self.sm.update_requirement_status(req_id, 'completed')
        logger.info(f"Требование {req_id} завершено")
    
    def get_pending_requirements(self) -> List[Dict[str, str]]:
        """
        Возвращает список необработанных требований.
        
        Returns:
            Список требований с id и кратким текстом
        """
        # Убеждаемся что сессия загружена
        session = self.sm.load()
        if not session:
            logger.warning("Сессия не найдена")
            return []
        
        pending = self.sm.get_pending_requirements()
        return [
            {
                'id': req.id,
                'text': req.text[:100] + '...' if len(req.text) > 100 else req.text,
                'source': req.source
            }
            for req in pending
        ]
    
    def get_requirement_text(self, req_id: str) -> str:
        """Возвращает полный текст требования."""
        req = self.sm.find_requirement_by_id(req_id)
        if not req:
            raise ValueError(f"Требование {req_id} не найдено")
        return req.text
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Возвращает статистику по генерации.
        
        Returns:
            Словарь со статистикой
        """
        session = self.sm.load()
        if not session:
            return {}
        
        completed_reqs = [r for r in session.requirements if r.status.value == 'completed']
        total_tests = sum(len(r.test_cases) for r in session.requirements)
        
        return {
            'total_requirements': len(session.requirements),
            'completed_requirements': len(completed_reqs),
            'pending_requirements': len(session.requirements) - len(completed_reqs),
            'total_test_cases': total_tests,
            'session_id': session.session_id
        }


def create_boundary_test_cases(
    req_id: str,
    base_tc_id: str,
    field_name: str,
    min_value: Any,
    max_value: Any,
    valid_example: Any,
    invalid_low: Any,
    invalid_high: Any,
    preconditions: List[str] = None,
    endpoint: str = "",
    http_method: str = "POST"
) -> List[Dict[str, Any]]:
    """
    Генерирует набор тест-кейсов для граничных значений (BVA).

    Args:
        req_id: ID требования
        base_tc_id: Базовый ID (например, TC-003)
        field_name: Название поля
        min_value: Минимальное валидное значение
        max_value: Максимальное валидное значение
        valid_example: Пример валидного значения
        invalid_low: Невалидное значение (ниже минимума)
        invalid_high: Невалидное значение (выше максимума)
        preconditions: Общие предусловия
        endpoint: Endpoint для тестирования
        http_method: HTTP метод

    Returns:
        Список тест-кейсов
    """
    preconditions = preconditions or ['API сервер доступен']

    return [
        {
            'id': f'{base_tc_id}-BVA-001',
            'title': f'Граничное значение {field_name}: минимум ({min_value})',
            'priority': 'High',
            'test_type': 'Boundary',
            'technique': 'BVA: Min Boundary',
            'preconditions': preconditions,
            'steps': [
                {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': {field_name: min_value}},
                {'step': 2, 'action': 'Проверить код ответа'},
                {'step': 3, 'action': f'Проверить значение {field_name} в ответе'}
            ],
            'expected_result': f'1. Код ответа: 200 OK или 201 Created\n2. Response body содержит: {field_name}: {min_value}\n3. Значение принято системой'
        },
        {
            'id': f'{base_tc_id}-BVA-002',
            'title': f'Граничное значение {field_name}: максимум ({max_value})',
            'priority': 'High',
            'test_type': 'Boundary',
            'technique': 'BVA: Max Boundary',
            'preconditions': preconditions,
            'steps': [
                {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': {field_name: max_value}},
                {'step': 2, 'action': 'Проверить код ответа'},
                {'step': 3, 'action': f'Проверить значение {field_name} в ответе'}
            ],
            'expected_result': f'1. Код ответа: 200 OK или 201 Created\n2. Response body содержит: {field_name}: {max_value}\n3. Значение принято системой'
        },
        {
            'id': f'{base_tc_id}-BVA-003',
            'title': f'Невалидное значение {field_name}: ниже минимума ({invalid_low})',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'BVA: Below Min',
            'preconditions': preconditions,
            'steps': [
                {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': {field_name: invalid_low}},
                {'step': 2, 'action': 'Проверить код ответа'},
                {'step': 3, 'action': 'Проверить сообщение об ошибке'}
            ],
            'expected_result': f'1. Код ответа: 400 Bad Request\n2. Response body содержит: message с описанием ошибки для {field_name}\n3. Объект НЕ создан/изменен'
        },
        {
            'id': f'{base_tc_id}-BVA-004',
            'title': f'Невалидное значение {field_name}: выше максимума ({invalid_high})',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'BVA: Above Max',
            'preconditions': preconditions,
            'steps': [
                {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': {field_name: invalid_high}},
                {'step': 2, 'action': 'Проверить код ответа'},
                {'step': 3, 'action': 'Проверить сообщение об ошибке'}
            ],
            'expected_result': f'1. Код ответа: 400 Bad Request\n2. Response body содержит: message с описанием ошибки для {field_name}\n3. Объект НЕ создан/изменен'
        }
    ]


def create_equivalence_test_cases(
    req_id: str,
    base_tc_id: str,
    field_name: str,
    valid_values: List[Any],
    invalid_values: List[Any],
    preconditions: List[str] = None,
    endpoint: str = "",
    http_method: str = "POST"
) -> List[Dict[str, Any]]:
    """
    Генерирует набор тест-кейсов для классов эквивалентности (EP).

    Args:
        req_id: ID требования
        base_tc_id: Базовый ID
        field_name: Название поля
        valid_values: Список валидных значений
        invalid_values: Список невалидных значений
        preconditions: Общие предусловия
        endpoint: Endpoint для тестирования
        http_method: HTTP метод

    Returns:
        Список тест-кейсов
    """
    preconditions = preconditions or ['API сервер доступен']
    test_cases = []

    # Валидные значения
    for idx, value in enumerate(valid_values, 1):
        test_cases.append({
            'id': f'{base_tc_id}-EP-{idx:03d}',
            'title': f'Валидное значение {field_name}: {value}',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'EP: Valid Class',
            'preconditions': preconditions,
            'steps': [
                {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': {field_name: value}},
                {'step': 2, 'action': 'Проверить код ответа'},
                {'step': 3, 'action': f'Проверить значение {field_name} в ответе'}
            ],
            'expected_result': f'1. Код ответа: 200 OK или 201 Created\n2. Response body содержит: {field_name}: "{value}"\n3. Значение принято системой'
        })

    # Невалидные значения
    for idx, value in enumerate(invalid_values, len(valid_values) + 1):
        display_value = value if value else "(пустое значение)"
        test_cases.append({
            'id': f'{base_tc_id}-EP-{idx:03d}',
            'title': f'Невалидное значение {field_name}: {display_value}',
            'priority': 'Medium',
            'test_type': 'Negative',
            'technique': 'EP: Invalid Class',
            'preconditions': preconditions,
            'steps': [
                {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': {field_name: value}},
                {'step': 2, 'action': 'Проверить код ответа'},
                {'step': 3, 'action': 'Проверить сообщение об ошибке'}
            ],
            'expected_result': f'1. Код ответа: 400 Bad Request\n2. Response body содержит: message с ошибкой валидации {field_name}\n3. Объект НЕ создан/изменен'
        })

    return test_cases


def create_api_crud_test_suite(
    req_id: str,
    base_tc_id: str,
    endpoint: str,
    http_method: str,
    req_type: str,
    preconditions: List[str] = None,
    sample_data: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Генерирует полный набор тест-кейсов для CRUD операций API.

    Args:
        req_id: ID требования
        base_tc_id: Базовый ID
        endpoint: API endpoint
        http_method: HTTP метод (GET, POST, PUT, DELETE)
        req_type: Тип требования ('create', 'read', 'update', 'delete', 'search')
        preconditions: Общие предусловия
        sample_data: Пример данных для request body

    Returns:
        Список тест-кейсов для типовых сценариев
    """
    preconditions = preconditions or ['API сервер доступен']
    sample_data = sample_data or {'id': 100, 'name': 'TestObject'}
    test_cases = []

    if req_type == 'create':
        test_cases.extend([
            {
                'id': f'{base_tc_id}-CRUD-001',
                'title': 'Успешное создание с валидными данными',
                'priority': 'Critical',
                'test_type': 'Positive',
                'technique': 'Use Case Testing: Happy Path',
                'preconditions': preconditions,
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': sample_data},
                    {'step': 2, 'action': 'Проверить код ответа'},
                    {'step': 3, 'action': 'Проверить структуру response body'},
                    {'step': 4, 'action': f'Выполнить GET {endpoint}/{{id}} для верификации'}
                ],
                'expected_result': f'1. Код ответа: 201 Created\n2. Response body содержит:\n   - id: {sample_data.get("id", "<auto>")}\n   - name: "{sample_data.get("name", "TestObject")}"\n3. GET возвращает созданный объект\n4. Все поля совпадают с отправленными'
            },
            {
                'id': f'{base_tc_id}-CRUD-002',
                'title': 'Создание с дубликатом идентификатора',
                'priority': 'High',
                'test_type': 'Negative',
                'technique': 'Error Guessing: Duplicate ID',
                'preconditions': preconditions + [f'Объект с id={sample_data.get("id", 100)} уже существует'],
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': sample_data},
                    {'step': 2, 'action': 'Проверить код ответа'},
                    {'step': 3, 'action': 'Проверить сообщение об ошибке'}
                ],
                'expected_result': '1. Код ответа: 409 Conflict\n2. Response body содержит:\n   - code: 409\n   - message: указывает на дубликат\n3. Новый объект НЕ создан'
            },
            {
                'id': f'{base_tc_id}-CRUD-003',
                'title': 'Создание без обязательных полей',
                'priority': 'High',
                'test_type': 'Negative',
                'technique': 'EP: Missing Required Fields',
                'preconditions': preconditions,
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': {}},
                    {'step': 2, 'action': 'Проверить код ответа'},
                    {'step': 3, 'action': 'Проверить сообщение об ошибке валидации'}
                ],
                'expected_result': '1. Код ответа: 400 Bad Request\n2. Response body содержит:\n   - code: 400\n   - message: "Validation failed" или перечень пропущенных полей\n3. Объект НЕ создан'
            }
        ])

    elif req_type == 'read':
        test_cases.extend([
            {
                'id': f'{base_tc_id}-CRUD-001',
                'title': 'Успешное получение существующего объекта',
                'priority': 'Critical',
                'test_type': 'Positive',
                'technique': 'Use Case Testing: Happy Path',
                'preconditions': preconditions + ['Объект с указанным ID существует'],
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint}/100'},
                    {'step': 2, 'action': 'Проверить код ответа'},
                    {'step': 3, 'action': 'Проверить структуру response body'}
                ],
                'expected_result': '1. Код ответа: 200 OK\n2. Response body содержит:\n   - id: 100\n   - name, status и другие поля объекта\n3. Content-Type: application/json'
            },
            {
                'id': f'{base_tc_id}-CRUD-002',
                'title': 'Получение несуществующего объекта',
                'priority': 'High',
                'test_type': 'Negative',
                'technique': 'EP: Non-existent Resource',
                'preconditions': preconditions,
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint}/999999'},
                    {'step': 2, 'action': 'Проверить код ответа'},
                    {'step': 3, 'action': 'Проверить сообщение'}
                ],
                'expected_result': '1. Код ответа: 404 Not Found\n2. Response body содержит:\n   - code: 404\n   - message: "not found" или аналог'
            },
            {
                'id': f'{base_tc_id}-CRUD-003',
                'title': 'Получение с невалидным ID',
                'priority': 'Medium',
                'test_type': 'Negative',
                'technique': 'Error Guessing: Invalid ID Format',
                'preconditions': preconditions,
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint}/invalid'},
                    {'step': 2, 'action': 'Проверить код ответа'},
                    {'step': 3, 'action': f'Отправить {http_method} {endpoint}/-1'},
                    {'step': 4, 'action': 'Проверить код ответа'}
                ],
                'expected_result': '1. Код ответа: 400 Bad Request для нечислового ID\n2. Код ответа: 400 Bad Request для отрицательного ID\n3. Response body содержит сообщение об ошибке'
            }
        ])

    elif req_type == 'update':
        updated_data = {**sample_data, 'name': 'UpdatedName'}
        test_cases.extend([
            {
                'id': f'{base_tc_id}-CRUD-001',
                'title': 'Успешное обновление существующего объекта',
                'priority': 'Critical',
                'test_type': 'Positive',
                'technique': 'Use Case Testing: Happy Path',
                'preconditions': preconditions + ['Объект существует'],
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': updated_data},
                    {'step': 2, 'action': 'Проверить код ответа'},
                    {'step': 3, 'action': 'Проверить обновленные данные в ответе'},
                    {'step': 4, 'action': f'Выполнить GET {endpoint}/{{id}} для верификации'}
                ],
                'expected_result': f'1. Код ответа: 200 OK\n2. Response body содержит обновленные данные:\n   - name: "UpdatedName"\n3. GET подтверждает изменения'
            },
            {
                'id': f'{base_tc_id}-CRUD-002',
                'title': 'Обновление несуществующего объекта',
                'priority': 'High',
                'test_type': 'Negative',
                'technique': 'EP: Non-existent Resource',
                'preconditions': preconditions,
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': {'id': 999999, 'name': 'Test'}},
                    {'step': 2, 'action': 'Проверить код ответа'}
                ],
                'expected_result': '1. Код ответа: 404 Not Found\n2. Объект НЕ создан'
            },
            {
                'id': f'{base_tc_id}-CRUD-003',
                'title': 'Обновление с невалидными данными',
                'priority': 'Medium',
                'test_type': 'Negative',
                'technique': 'Error Guessing: Invalid Data',
                'preconditions': preconditions + ['Объект существует'],
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': {'id': sample_data.get('id', 100), 'name': ''}},
                    {'step': 2, 'action': 'Проверить код ответа'},
                    {'step': 3, 'action': 'Проверить сообщение об ошибке'}
                ],
                'expected_result': '1. Код ответа: 400 Bad Request\n2. Response body содержит ошибку валидации\n3. Объект НЕ изменен'
            }
        ])

    elif req_type == 'delete':
        test_cases.extend([
            {
                'id': f'{base_tc_id}-CRUD-001',
                'title': 'Успешное удаление существующего объекта',
                'priority': 'Critical',
                'test_type': 'Positive',
                'technique': 'Use Case Testing: Happy Path',
                'preconditions': preconditions + ['Объект с id=100 существует'],
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint}/100'},
                    {'step': 2, 'action': 'Проверить код ответа'},
                    {'step': 3, 'action': f'Выполнить GET {endpoint}/100 для верификации удаления'}
                ],
                'expected_result': '1. Код ответа: 200 OK или 204 No Content\n2. GET {endpoint}/100 возвращает 404 Not Found\n3. Объект удален из системы'
            },
            {
                'id': f'{base_tc_id}-CRUD-002',
                'title': 'Удаление несуществующего объекта',
                'priority': 'High',
                'test_type': 'Negative',
                'technique': 'EP: Non-existent Resource',
                'preconditions': preconditions,
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint}/999999'},
                    {'step': 2, 'action': 'Проверить код ответа'}
                ],
                'expected_result': '1. Код ответа: 404 Not Found'
            },
            {
                'id': f'{base_tc_id}-CRUD-003',
                'title': 'Идемпотентность: повторное удаление',
                'priority': 'Medium',
                'test_type': 'Positive',
                'technique': 'Specification: Idempotency',
                'preconditions': preconditions + ['Объект был удален в предыдущем тесте'],
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint}/100 повторно'},
                    {'step': 2, 'action': 'Проверить код ответа'}
                ],
                'expected_result': '1. Код ответа: 404 Not Found\n2. Повторный DELETE не вызывает ошибок сервера\n3. Идемпотентное поведение подтверждено'
            }
        ])

    elif req_type == 'search':
        test_cases.extend([
            {
                'id': f'{base_tc_id}-CRUD-001',
                'title': 'Поиск с валидными параметрами (найдены результаты)',
                'priority': 'Critical',
                'test_type': 'Positive',
                'technique': 'Use Case Testing: Happy Path',
                'preconditions': preconditions + ['Существуют объекты с искомым статусом'],
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint}?status=available'},
                    {'step': 2, 'action': 'Проверить код ответа'},
                    {'step': 3, 'action': 'Проверить структуру массива в ответе'}
                ],
                'expected_result': '1. Код ответа: 200 OK\n2. Response body: массив объектов []\n3. Каждый объект содержит id, name, status\n4. Все объекты имеют status: "available"'
            },
            {
                'id': f'{base_tc_id}-CRUD-002',
                'title': 'Поиск без результатов',
                'priority': 'Medium',
                'test_type': 'Positive',
                'technique': 'EP: Empty Result Set',
                'preconditions': preconditions,
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint}?status=nonexistent'},
                    {'step': 2, 'action': 'Проверить код ответа'},
                    {'step': 3, 'action': 'Проверить пустой массив в ответе'}
                ],
                'expected_result': '1. Код ответа: 200 OK\n2. Response body: пустой массив []\n3. Никаких ошибок не возникает'
            },
            {
                'id': f'{base_tc_id}-CRUD-003',
                'title': 'Поиск с невалидными параметрами',
                'priority': 'Medium',
                'test_type': 'Negative',
                'technique': 'Error Guessing: Invalid Parameters',
                'preconditions': preconditions,
                'steps': [
                    {'step': 1, 'action': f'Отправить {http_method} {endpoint}?status=INVALID_STATUS'},
                    {'step': 2, 'action': 'Проверить код ответа'},
                    {'step': 3, 'action': 'Проверить сообщение об ошибке'}
                ],
                'expected_result': '1. Код ответа: 400 Bad Request\n2. Response body содержит описание ошибки валидации параметра status'
            }
        ])

    return test_cases


def create_validation_test_cases(
    req_id: str,
    base_tc_id: str,
    endpoint: str,
    http_method: str,
    fields_validation: Dict[str, str],
    preconditions: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Генерирует тест-кейсы для проверки валидации полей.
    
    Args:
        req_id: ID требования
        base_tc_id: Базовый ID
        endpoint: API endpoint
        http_method: HTTP метод
        fields_validation: Словарь {field_name: validation_rule}
                          Например: {'email': 'формат email', 'phone': 'формат телефона'}
        preconditions: Общие предусловия
    
    Returns:
        Список тест-кейсов валидации
    """
    preconditions = preconditions or ['API доступен']
    test_cases = []
    
    idx = 1
    for field, rule in fields_validation.items():
        test_cases.append({
            'id': f'{base_tc_id}-VAL-{idx:03d}',
            'title': f'Валидация {field}: некорректный формат',
            'priority': 'Medium',
            'test_type': 'Negative',
            'technique': 'equivalence_partitioning',
            'preconditions': preconditions,
            'steps': [
                {'step': 1, 'action': f'Подготовить JSON с некорректным {field} (нарушает {rule})'},
                {'step': 2, 'action': f'Отправить {http_method} {endpoint}'}
            ],
            'expected_result': f'Код ответа: 400 Bad Request. Ошибка валидации поля {field}'
        })
        idx += 1
        
        # Тест на пустое значение для обязательных полей
        if 'обязательн' in rule.lower() or 'required' in rule.lower():
            test_cases.append({
                'id': f'{base_tc_id}-VAL-{idx:03d}',
                'title': f'Валидация {field}: пустое значение',
                'priority': 'High',
                'test_type': 'Negative',
                'technique': 'equivalence_partitioning',
                'preconditions': preconditions,
                'steps': [
                    {'step': 1, 'action': f'Подготовить JSON с пустым {field}'},
                    {'step': 2, 'action': f'Отправить {http_method} {endpoint}'}
                ],
                'expected_result': f'Код ответа: 400 Bad Request. Поле {field} обязательно'
            })
            idx += 1
    
    return test_cases


def create_state_transition_tests(
    req_id: str,
    base_tc_id: str,
    endpoint: str,
    http_method: str,
    valid_transitions: List[Tuple[str, str]],
    invalid_transitions: List[Tuple[str, str]],
    preconditions: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Генерирует тест-кейсы для проверки переходов между состояниями.

    Args:
        req_id: ID требования
        base_tc_id: Базовый ID
        endpoint: API endpoint
        http_method: HTTP метод
        valid_transitions: Список валидных переходов [(from_state, to_state), ...]
        invalid_transitions: Список невалидных переходов
        preconditions: Общие предусловия

    Returns:
        Список тест-кейсов для переходов состояний
    """
    preconditions = preconditions or ['API сервер доступен']
    test_cases = []

    # Валидные переходы
    for idx, (from_state, to_state) in enumerate(valid_transitions, 1):
        test_cases.append({
            'id': f'{base_tc_id}-ST-{idx:03d}',
            'title': f'Валидный переход статуса: {from_state} → {to_state}',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'State Transition: Valid Path',
            'preconditions': preconditions + [f'Объект существует в состоянии "{from_state}"'],
            'steps': [
                {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': {'status': to_state}},
                {'step': 2, 'action': 'Проверить код ответа'},
                {'step': 3, 'action': 'Проверить новый статус в ответе'},
                {'step': 4, 'action': 'Выполнить GET для верификации'}
            ],
            'expected_result': f'1. Код ответа: 200 OK\n2. Response body содержит:\n   - status: "{to_state}"\n3. GET подтверждает изменение статуса\n4. Переход {from_state} → {to_state} успешен'
        })

    # Невалидные переходы
    for idx, (from_state, to_state) in enumerate(invalid_transitions, len(valid_transitions) + 1):
        test_cases.append({
            'id': f'{base_tc_id}-ST-{idx:03d}',
            'title': f'Невалидный переход статуса: {from_state} → {to_state}',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'State Transition: Invalid Path',
            'preconditions': preconditions + [f'Объект существует в состоянии "{from_state}"'],
            'steps': [
                {'step': 1, 'action': f'Отправить {http_method} {endpoint} с body:', 'request_body': {'status': to_state}},
                {'step': 2, 'action': 'Проверить код ответа'},
                {'step': 3, 'action': 'Проверить сообщение об ошибке'},
                {'step': 4, 'action': 'Выполнить GET для проверки что статус НЕ изменился'}
            ],
            'expected_result': f'1. Код ответа: 400 Bad Request или 409 Conflict\n2. Response body содержит:\n   - message: описание недопустимого перехода\n3. GET подтверждает: статус остался "{from_state}"\n4. Переход {from_state} → {to_state} заблокирован'
        })

    return test_cases


def create_performance_tests(
    req_id: str,
    base_tc_id: str,
    endpoint: str,
    http_method: str,
    max_response_time_ms: int,
    preconditions: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Генерирует базовые тест-кейсы производительности.

    Args:
        req_id: ID требования
        base_tc_id: Базовый ID
        endpoint: API endpoint
        http_method: HTTP метод
        max_response_time_ms: Максимальное допустимое время ответа в миллисекундах
        preconditions: Общие предусловия

    Returns:
        Список тест-кейсов производительности
    """
    preconditions = preconditions or ['API доступен']

    return [
        {
            'id': f'{base_tc_id}-PERF-001',
            'title': f'Проверка времени ответа (макс {max_response_time_ms}ms)',
            'priority': 'Medium',
            'test_type': 'Performance',
            'technique': 'performance_testing',
            'preconditions': preconditions,
            'steps': [
                {'step': 1, 'action': f'Отправить {http_method} {endpoint}'},
                {'step': 2, 'action': 'Измерить время ответа'}
            ],
            'expected_result': f'Время ответа не превышает {max_response_time_ms}ms'
        },
        {
            'id': f'{base_tc_id}-PERF-002',
            'title': 'Проверка идемпотентности (множественные запросы)',
            'priority': 'Medium',
            'test_type': 'Performance',
            'technique': 'specification_based',
            'preconditions': preconditions,
            'steps': [
                {'step': 1, 'action': f'Отправить {http_method} {endpoint} 5 раз подряд'},
                {'step': 2, 'action': 'Сравнить результаты'}
            ],
            'expected_result': 'Все ответы идентичны (для GET) или корректно обработаны (для других методов)'
        }
    ]


# =============================================================================
# Новые методы для UI и интеграционных тестов
# =============================================================================

def create_ui_test_case(
    base_tc_id: str,
    title: str,
    ui_element: str,
    priority: str = "Medium",
    preconditions: List[str] = None,
    steps: List[Dict[str, Any]] = None,
    expected_result: str = "",
    test_type: str = "Positive",
    technique: str = "ui_form",
    component: str = "frontend",
    tags: List[str] = None
) -> Dict[str, Any]:
    """
    Создает UI тест-кейс с расширенными полями.

    Args:
        base_tc_id: ID тест-кейса
        title: Название теста
        ui_element: UI элемент (кнопка, форма, и т.д.)
        priority: Приоритет
        preconditions: Предусловия
        steps: Шаги теста
        expected_result: Ожидаемый результат
        test_type: Тип теста
        technique: Техника (ui_form, ui_calendar, ui_file_upload)
        component: Компонент (frontend, fullstack)
        tags: Дополнительные теги

    Returns:
        Словарь с тест-кейсом
    """
    return {
        'id': base_tc_id,
        'title': title,
        'priority': priority,
        'test_type': test_type,
        'technique': technique,
        'preconditions': preconditions or ['Страница загружена', 'Пользователь авторизован'],
        'steps': steps or [],
        'expected_result': expected_result,
        'layer': 'ui',
        'component': component,
        'tags': tags or ['ui'],
        'ui_element': ui_element,
        'api_endpoint': None
    }


def create_integration_test_case(
    base_tc_id: str,
    title: str,
    api_endpoint: str = None,
    priority: str = "High",
    preconditions: List[str] = None,
    steps: List[Dict[str, Any]] = None,
    expected_result: str = "",
    test_type: str = "Positive",
    technique: str = "backend_frontend_integration",
    component: str = "fullstack",
    tags: List[str] = None
) -> Dict[str, Any]:
    """
    Создает интеграционный тест-кейс.

    Args:
        base_tc_id: ID тест-кейса
        title: Название теста
        api_endpoint: API эндпоинт (если применимо)
        priority: Приоритет
        preconditions: Предусловия
        steps: Шаги теста
        expected_result: Ожидаемый результат
        test_type: Тип теста
        technique: Техника
        component: Компонент
        tags: Дополнительные теги

    Returns:
        Словарь с тест-кейсом
    """
    return {
        'id': base_tc_id,
        'title': title,
        'priority': priority,
        'test_type': test_type,
        'technique': technique,
        'preconditions': preconditions or ['Система доступна', 'Все сервисы работают'],
        'steps': steps or [],
        'expected_result': expected_result,
        'layer': 'integration',
        'component': component,
        'tags': tags or ['integration'],
        'ui_element': None,
        'api_endpoint': api_endpoint
    }


def create_file_upload_tests(
    req_id: str,
    base_tc_id: str,
    allowed_formats: List[str],
    max_size_mb: float | None,
    max_files: int = 1,
    preconditions: List[str] = None,
    ui_element: str = "file-upload"
) -> List[Dict[str, Any]]:
    """
    Генерирует набор тест-кейсов для загрузки файлов.

    Args:
        req_id: ID требования
        base_tc_id: Базовый ID
        allowed_formats: Допустимые форматы (например, ['jpg', 'png'])
        max_size_mb: Максимальный размер в МБ (если задан)
        max_files: Максимальное количество файлов
        preconditions: Общие предусловия
        ui_element: Название UI элемента

    Returns:
        Список тест-кейсов
    """
    preconditions = preconditions or ['Страница загрузки файлов открыта']
    formats_str = ', '.join(allowed_formats).upper()
    size_hint = f' размером < {max_size_mb} MB' if max_size_mb else ''

    test_cases = [
        # Позитивные тесты
        {
            'id': f'{base_tc_id}-UPLOAD-001',
            'title': f'Успешная загрузка файла допустимого формата ({formats_str})',
            'priority': 'Critical',
            'test_type': 'Positive',
            'technique': 'ui_file_upload',
            'preconditions': preconditions + [f'Подготовлен файл test.{allowed_formats[0]}{size_hint}'],
            'steps': [
                {'step': 1, 'action': 'Кликнуть на зону загрузки'},
                {'step': 2, 'action': f'Выбрать файл test.{allowed_formats[0]}'},
                {'step': 3, 'action': 'Дождаться завершения загрузки'}
            ],
            'expected_result': f'1. Показывается индикатор прогресса\\n2. Файл успешно загружен\\n3. Отображается превью/имя файла',
            'layer': 'ui',
            'component': 'fullstack',
            'tags': ['upload', 'ui'],
            'ui_element': ui_element
        },
        {
            'id': f'{base_tc_id}-UPLOAD-002',
            'title': 'Загрузка файла через drag-and-drop',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'ui_file_upload',
            'preconditions': preconditions,
            'steps': [
                {'step': 1, 'action': 'Перетащить файл на зону загрузки'},
                {'step': 2, 'action': 'Отпустить файл'},
                {'step': 3, 'action': 'Проверить результат'}
            ],
            'expected_result': '1. Зона подсвечивается при наведении\\n2. Файл загружается\\n3. Отображается превью',
            'layer': 'ui',
            'component': 'fullstack',
            'tags': ['upload', 'drag-drop', 'ui'],
            'ui_element': ui_element
        },
    ]

    if max_files and max_files > 1:
        test_cases.extend([
            {
                'id': f'{base_tc_id}-UPLOAD-006',
                'title': f'Успешная загрузка максимального количества файлов ({max_files})',
                'priority': 'High',
                'test_type': 'Boundary',
                'technique': 'ui_file_upload',
                'preconditions': preconditions + [
                    f'Подготовлены {max_files} файла(ов) формата {formats_str}{size_hint}'
                ],
                'steps': [
                    {'step': 1, 'action': f'Выбрать {max_files} файлов для загрузки'},
                    {'step': 2, 'action': 'Дождаться завершения загрузки'}
                ],
                'expected_result': f'1. Загружены все {max_files} файлов\\n2. Отображаются все превью/имена',
                'layer': 'ui',
                'component': 'fullstack',
                'tags': ['upload', 'boundary', 'ui'],
                'ui_element': ui_element
            },
            {
                'id': f'{base_tc_id}-UPLOAD-007',
                'title': f'Отклонение загрузки при превышении лимита файлов ({max_files + 1})',
                'priority': 'High',
                'test_type': 'Negative',
                'technique': 'ui_file_upload',
                'preconditions': preconditions + [
                    f'Подготовлены {max_files + 1} файлов формата {formats_str}{size_hint}'
                ],
                'steps': [
                    {'step': 1, 'action': f'Выбрать {max_files + 1} файлов для загрузки'},
                    {'step': 2, 'action': 'Проверить сообщение об ошибке'}
                ],
                'expected_result': f'1. Загрузка отклонена или ограничена до {max_files} файлов\\n2. Сообщение о лимите количества файлов',
                'layer': 'ui',
                'component': 'frontend',
                'tags': ['upload', 'validation', 'ui'],
                'ui_element': ui_element
            },
        ])

    test_cases.extend([
        # Негативные тесты
        {
            'id': f'{base_tc_id}-UPLOAD-003',
            'title': 'Отклонение файла недопустимого формата',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'ui_file_upload',
            'preconditions': preconditions + ['Подготовлен файл недопустимого формата (например, .exe)'],
            'steps': [
                {'step': 1, 'action': 'Попытаться загрузить файл недопустимого формата'},
                {'step': 2, 'action': 'Проверить сообщение об ошибке'}
            ],
            'expected_result': f'1. Файл не загружается\\n2. Сообщение: "Допустимые форматы: {formats_str}"',
            'layer': 'ui',
            'component': 'frontend',
            'tags': ['upload', 'validation', 'ui'],
            'ui_element': ui_element
        },
        *([] if not max_size_mb else [{
            'id': f'{base_tc_id}-UPLOAD-004',
            'title': f'Отклонение файла превышающего лимит ({max_size_mb} MB)',
            'priority': 'High',
            'test_type': 'Boundary',
            'technique': 'ui_file_upload',
            'preconditions': preconditions + [f'Подготовлен файл размером > {max_size_mb} MB'],
            'steps': [
                {'step': 1, 'action': 'Попытаться загрузить файл превышающий лимит'},
                {'step': 2, 'action': 'Проверить валидацию'}
            ],
            'expected_result': f'1. Файл не загружается\\n2. Сообщение: "Максимальный размер: {max_size_mb} MB"',
            'layer': 'ui',
            'component': 'frontend',
            'tags': ['upload', 'boundary', 'ui'],
            'ui_element': ui_element
        }]),
        {
            'id': f'{base_tc_id}-UPLOAD-005',
            'title': 'Удаление загруженного файла',
            'priority': 'Medium',
            'test_type': 'Positive',
            'technique': 'ui_file_upload',
            'preconditions': preconditions + ['Файл успешно загружен'],
            'steps': [
                {'step': 1, 'action': 'Кликнуть на кнопку удаления файла'},
                {'step': 2, 'action': 'Подтвердить удаление (если есть диалог)'}
            ],
            'expected_result': '1. Файл удален\\n2. Зона загрузки возвращается в исходное состояние',
            'layer': 'ui',
            'component': 'fullstack',
            'tags': ['upload', 'delete', 'ui'],
            'ui_element': ui_element
        }
    ])

    return test_cases


def create_calendar_tests(
    req_id: str,
    base_tc_id: str,
    min_date: str = "today",
    max_date: str = None,
    has_range: bool = False,
    preconditions: List[str] = None,
    ui_element: str = "date-picker"
) -> List[Dict[str, Any]]:
    """
    Генерирует набор тест-кейсов для календаря.

    Args:
        req_id: ID требования
        base_tc_id: Базовый ID
        min_date: Минимальная дата ("today" или конкретная дата)
        max_date: Максимальная дата (если есть ограничение)
        has_range: Поддерживает ли выбор диапазона дат
        preconditions: Общие предусловия
        ui_element: Название UI элемента

    Returns:
        Список тест-кейсов
    """
    preconditions = preconditions or ['Страница с календарем открыта']

    test_cases = [
        # Базовые тесты
        {
            'id': f'{base_tc_id}-CAL-001',
            'title': 'Открытие календаря при клике на поле даты',
            'priority': 'Critical',
            'test_type': 'Positive',
            'technique': 'ui_calendar',
            'preconditions': preconditions,
            'steps': [
                {'step': 1, 'action': 'Кликнуть на поле ввода даты'},
                {'step': 2, 'action': 'Наблюдать появление календаря'}
            ],
            'expected_result': '1. Календарь появляется\\n2. Текущий месяц отображается\\n3. Сегодняшняя дата выделена',
            'layer': 'ui',
            'component': 'frontend',
            'tags': ['calendar', 'ui'],
            'ui_element': ui_element
        },
        {
            'id': f'{base_tc_id}-CAL-002',
            'title': 'Выбор даты кликом',
            'priority': 'Critical',
            'test_type': 'Positive',
            'technique': 'ui_calendar',
            'preconditions': preconditions + ['Календарь открыт'],
            'steps': [
                {'step': 1, 'action': 'Кликнуть на доступную дату'},
                {'step': 2, 'action': 'Проверить поле ввода'}
            ],
            'expected_result': '1. Календарь закрывается\\n2. Выбранная дата отображается в поле\\n3. Дата в корректном формате',
            'layer': 'ui',
            'component': 'frontend',
            'tags': ['calendar', 'ui'],
            'ui_element': ui_element
        },
        {
            'id': f'{base_tc_id}-CAL-003',
            'title': 'Навигация на следующий месяц',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'ui_calendar',
            'preconditions': preconditions + ['Календарь открыт'],
            'steps': [
                {'step': 1, 'action': 'Кликнуть на кнопку "Следующий месяц"'},
                {'step': 2, 'action': 'Проверить отображаемый месяц'}
            ],
            'expected_result': '1. Отображается следующий месяц\\n2. Заголовок месяца обновился',
            'layer': 'ui',
            'component': 'frontend',
            'tags': ['calendar', 'navigation', 'ui'],
            'ui_element': ui_element
        },
        {
            'id': f'{base_tc_id}-CAL-004',
            'title': 'Навигация на предыдущий месяц',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'ui_calendar',
            'preconditions': preconditions + ['Календарь открыт', 'Не на первом доступном месяце'],
            'steps': [
                {'step': 1, 'action': 'Кликнуть на кнопку "Предыдущий месяц"'},
                {'step': 2, 'action': 'Проверить отображаемый месяц'}
            ],
            'expected_result': '1. Отображается предыдущий месяц\\n2. Заголовок месяца обновился',
            'layer': 'ui',
            'component': 'frontend',
            'tags': ['calendar', 'navigation', 'ui'],
            'ui_element': ui_element
        },
        # Граничные тесты
        {
            'id': f'{base_tc_id}-CAL-005',
            'title': f'Попытка выбора даты до минимальной ({min_date})',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'ui_calendar',
            'preconditions': preconditions + ['Календарь открыт'],
            'steps': [
                {'step': 1, 'action': 'Найти дату раньше минимальной'},
                {'step': 2, 'action': 'Попытаться кликнуть на неё'}
            ],
            'expected_result': '1. Дата отображается как недоступная (серая)\\n2. Клик не выбирает дату\\n3. Календарь остаётся открытым',
            'layer': 'ui',
            'component': 'frontend',
            'tags': ['calendar', 'boundary', 'ui'],
            'ui_element': ui_element
        },
        {
            'id': f'{base_tc_id}-CAL-006',
            'title': 'Закрытие календаря при клике вне его',
            'priority': 'Medium',
            'test_type': 'Positive',
            'technique': 'ui_calendar',
            'preconditions': preconditions + ['Календарь открыт'],
            'steps': [
                {'step': 1, 'action': 'Кликнуть вне области календаря'},
                {'step': 2, 'action': 'Проверить состояние календаря'}
            ],
            'expected_result': '1. Календарь закрывается\\n2. Поле даты сохраняет предыдущее значение',
            'layer': 'ui',
            'component': 'frontend',
            'tags': ['calendar', 'ui'],
            'ui_element': ui_element
        }
    ]

    # Добавляем тесты для диапазона дат если поддерживается
    if has_range:
        test_cases.extend([
            {
                'id': f'{base_tc_id}-CAL-007',
                'title': 'Выбор диапазона дат',
                'priority': 'High',
                'test_type': 'Positive',
                'technique': 'ui_calendar',
                'preconditions': preconditions + ['Календарь открыт'],
                'steps': [
                    {'step': 1, 'action': 'Кликнуть на начальную дату'},
                    {'step': 2, 'action': 'Кликнуть на конечную дату'},
                    {'step': 3, 'action': 'Проверить выбранный диапазон'}
                ],
                'expected_result': '1. Диапазон визуально выделен\\n2. Обе даты отображаются в поле\\n3. Все даты в диапазоне подсвечены',
                'layer': 'ui',
                'component': 'frontend',
                'tags': ['calendar', 'range', 'ui'],
                'ui_element': ui_element
            },
            {
                'id': f'{base_tc_id}-CAL-008',
                'title': 'Попытка выбрать конечную дату раньше начальной',
                'priority': 'High',
                'test_type': 'Negative',
                'technique': 'ui_calendar',
                'preconditions': preconditions + ['Начальная дата выбрана'],
                'steps': [
                    {'step': 1, 'action': 'Попытаться выбрать дату раньше начальной'},
                    {'step': 2, 'action': 'Проверить поведение'}
                ],
                'expected_result': '1. Дата не выбирается как конечная ИЛИ\\n2. Начальная дата переопределяется на новую',
                'layer': 'ui',
                'component': 'frontend',
                'tags': ['calendar', 'range', 'boundary', 'ui'],
                'ui_element': ui_element
            }
        ])

    # Добавляем тест для максимальной даты если указана
    if max_date:
        test_cases.append({
            'id': f'{base_tc_id}-CAL-009',
            'title': f'Попытка выбора даты после максимальной ({max_date})',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'ui_calendar',
            'preconditions': preconditions + ['Календарь открыт'],
            'steps': [
                {'step': 1, 'action': 'Перейти к месяцу с максимальной датой'},
                {'step': 2, 'action': 'Попытаться выбрать дату после максимальной'}
            ],
            'expected_result': '1. Даты после максимальной недоступны\\n2. Клик не выбирает дату',
            'layer': 'ui',
            'component': 'frontend',
            'tags': ['calendar', 'boundary', 'ui'],
            'ui_element': ui_element
        })

    return test_cases
