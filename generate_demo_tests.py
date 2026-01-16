"""
Скрипт для генерации тест-кейсов по демо-требованиям Petstore.
Выполняет AGENT.md инструкции для demo/petstore.md.
"""
from src.utils.test_generator_helper import (
    TestGeneratorHelper,
    create_boundary_test_cases,
    create_equivalence_test_cases
)
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Файл для логирования замечаний
ISSUES_FILE = 'demo_generation_issues.txt'


def log_issue(issue: str):
    """Логирует замечание в файл."""
    with open(ISSUES_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{issue}\n")
    logger.warning(issue)


def main():
    """Основная функция генерации."""
    # Очистить файл замечаний
    with open(ISSUES_FILE, 'w', encoding='utf-8') as f:
        f.write("=== Замечания при генерации тестов для Petstore ===\n\n")
    
    helper = TestGeneratorHelper()
    
    # Получить необработанные требования
    pending = helper.get_pending_requirements()
    logger.info(f"Необработано требований: {len(pending)}")
    
    if not pending:
        log_issue("ОШИБКА: Нет необработанных требований. Запустите: ./venv/bin/python main.py load-demo -n petstore")
        return
    
    # Обрабатываем каждое требование
    for idx, req_info in enumerate(pending, 1):
        req_id = req_info['id']
        req_text = helper.get_requirement_text(req_id)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"[{idx}/{len(pending)}] Обработка: {req_id}")
        logger.info(f"{'='*60}")
        logger.info(f"Текст: {req_text[:200]}...")
        
        try:
            # Генерация тестов в зависимости от требования
            if req_id == 'REQ-001':
                generate_req_001(helper, req_id)
            elif req_id == 'REQ-002':
                generate_req_002(helper, req_id)
            elif req_id == 'REQ-003':
                generate_req_003(helper, req_id)
            elif req_id == 'REQ-004':
                generate_req_004(helper, req_id)
            elif req_id == 'REQ-005':
                generate_req_005(helper, req_id)
            elif req_id == 'REQ-006':
                generate_req_006(helper, req_id)
            elif req_id == 'REQ-007':
                generate_req_007(helper, req_id)
            else:
                # Для остальных создаем базовый набор
                generate_basic_tests(helper, req_id)
            
            # Отметить как завершенное
            helper.mark_requirement_completed(req_id)
            logger.info(f"✓ {req_id} завершено")
            
        except Exception as e:
            log_issue(f"ОШИБКА при обработке {req_id}: {str(e)}")
            logger.error(f"Ошибка: {e}", exc_info=True)
    
    # Статистика
    stats = helper.get_statistics()
    logger.info(f"\n{'='*60}")
    logger.info("ИТОГОВАЯ СТАТИСТИКА")
    logger.info(f"{'='*60}")
    logger.info(f"Всего требований: {stats['total_requirements']}")
    logger.info(f"Обработано: {stats['completed_requirements']}")
    logger.info(f"Осталось: {stats['pending_requirements']}")
    logger.info(f"Всего тест-кейсов: {stats['total_test_cases']}")
    logger.info(f"Сессия: {stats['session_id']}")
    logger.info(f"\nЗамечания сохранены в: {ISSUES_FILE}")


def generate_req_001(helper: TestGeneratorHelper, req_id: str):
    """REQ-001: POST /pet - Добавление питомца."""
    
    # Анализ требования
    helper.add_analysis(
        req_id=req_id,
        inputs=['id', 'name', 'category', 'photoUrls', 'tags', 'status'],
        outputs=['201 Created', '400 Bad Request', '409 Conflict'],
        business_rules=[
            'id > 0',
            'name: 2-50 символов, только буквы и дефис',
            'photoUrls: минимум 1 URL',
            'status: available|pending|sold (default: available)',
            'Дубликат id -> 409 Conflict'
        ],
        states=['available', 'pending', 'sold'],
        suggested_techniques=['boundary_value', 'equivalence_partitioning', 'error_guessing']
    )
    
    # BVA тесты для поля name (длина 2-50)
    name_bva = create_boundary_test_cases(
        req_id=req_id,
        base_tc_id='TC-001',
        field_name='name',
        min_value='AB',
        max_value='A' * 50,
        valid_example='ValidPetName',
        invalid_low='A',
        invalid_high='A' * 51,
        endpoint='POST /pet'
    )
    helper.add_test_cases_bulk(req_id, name_bva)
    
    # EP тесты для поля status
    status_ep = create_equivalence_test_cases(
        req_id=req_id,
        base_tc_id='TC-001',
        field_name='status',
        valid_values=['available', 'pending', 'sold'],
        invalid_values=['unknown', 'deleted', ''],
        endpoint='POST /pet'
    )
    helper.add_test_cases_bulk(req_id, status_ep)
    
    # Дополнительные тесты
    additional_tests = [
        {
            'id': 'TC-001-010',
            'title': 'Успешное создание с минимальными данными',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Подготовить JSON с обязательными полями: name, photoUrls'},
                {'step': 2, 'action': 'Отправить POST /pet'}
            ],
            'expected_result': 'Код ответа: 201 Created. Питомец создан с status=available по умолчанию'
        },
        {
            'id': 'TC-001-011',
            'title': 'Создание с дубликатом id',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'error_guessing',
            'preconditions': ['API доступен', 'Питомец с id=123 уже существует'],
            'steps': [
                {'step': 1, 'action': 'Подготовить JSON с существующим id=123'},
                {'step': 2, 'action': 'Отправить POST /pet'}
            ],
            'expected_result': 'Код ответа: 409 Conflict. Сообщение об ошибке дубликата'
        },
        {
            'id': 'TC-001-012',
            'title': 'Name с недопустимыми символами (цифры)',
            'priority': 'Medium',
            'test_type': 'Negative',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Подготовить JSON с name="Pet123"'},
                {'step': 2, 'action': 'Отправить POST /pet'}
            ],
            'expected_result': 'Код ответа: 400 Bad Request. Ошибка валидации name'
        },
        {
            'id': 'TC-001-013',
            'title': 'PhotoUrls пустой массив',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'boundary_value',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Подготовить JSON с photoUrls=[]'},
                {'step': 2, 'action': 'Отправить POST /pet'}
            ],
            'expected_result': 'Код ответа: 400 Bad Request. Требуется минимум 1 URL'
        }
    ]
    helper.add_test_cases_bulk(req_id, additional_tests)


def generate_req_002(helper: TestGeneratorHelper, req_id: str):
    """REQ-002: GET /pet/{petId} - Получение питомца по ID."""
    
    helper.add_analysis(
        req_id=req_id,
        inputs=['petId'],
        outputs=['200 OK', '400 Bad Request', '404 Not Found'],
        business_rules=[
            'petId должен быть положительным числом',
            'Время ответа <= 500ms',
            'Идемпотентный метод'
        ],
        suggested_techniques=['boundary_value', 'equivalence_partitioning']
    )
    
    # BVA тесты для petId
    petid_bva = create_boundary_test_cases(
        req_id=req_id,
        base_tc_id='TC-002',
        field_name='petId',
        min_value=1,
        max_value=9999999,
        valid_example=123,
        invalid_low=0,
        invalid_high=-1,
        endpoint='GET /pet/{petId}'
    )
    helper.add_test_cases_bulk(req_id, petid_bva)
    
    additional_tests = [
        {
            'id': 'TC-002-010',
            'title': 'Получение существующего питомца',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен', 'Питомец с id=123 существует'],
            'steps': [
                {'step': 1, 'action': 'Отправить GET /pet/123'}
            ],
            'expected_result': 'Код ответа: 200 OK. JSON с данными питомца id=123'
        },
        {
            'id': 'TC-002-011',
            'title': 'Получение несуществующего питомца',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Отправить GET /pet/999999'}
            ],
            'expected_result': 'Код ответа: 404 Not Found'
        },
        {
            'id': 'TC-002-012',
            'title': 'petId не является числом',
            'priority': 'Medium',
            'test_type': 'Negative',
            'technique': 'error_guessing',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Отправить GET /pet/abc'}
            ],
            'expected_result': 'Код ответа: 400 Bad Request. Ошибка валидации'
        },
        {
            'id': 'TC-002-013',
            'title': 'Проверка времени ответа',
            'priority': 'Medium',
            'test_type': 'Performance',
            'technique': 'performance_testing',
            'preconditions': ['API доступен', 'Питомец с id=123 существует'],
            'steps': [
                {'step': 1, 'action': 'Отправить GET /pet/123'},
                {'step': 2, 'action': 'Измерить время ответа'}
            ],
            'expected_result': 'Время ответа не превышает 500ms'
        }
    ]
    helper.add_test_cases_bulk(req_id, additional_tests)


def generate_req_003(helper: TestGeneratorHelper, req_id: str):
    """REQ-003: GET /pet/findByStatus - Поиск по статусу."""
    
    helper.add_analysis(
        req_id=req_id,
        inputs=['status'],
        outputs=['200 OK', '400 Bad Request'],
        business_rules=[
            'status: available|pending|sold',
            'Поддержка нескольких значений через запятую',
            'Пустой массив если ничего не найдено',
            'Максимум 100 записей',
            'Сортировка по дате (новые -> старые)',
            'Время выполнения <= 1 сек'
        ],
        states=['available', 'pending', 'sold'],
        suggested_techniques=['equivalence_partitioning', 'error_guessing']
    )
    
    # EP тесты для статуса
    status_ep = create_equivalence_test_cases(
        req_id=req_id,
        base_tc_id='TC-003',
        field_name='status',
        valid_values=['available', 'pending', 'sold'],
        invalid_values=['unknown', 'deleted', ''],
        endpoint='GET /pet/findByStatus'
    )
    helper.add_test_cases_bulk(req_id, status_ep)
    
    additional_tests = [
        {
            'id': 'TC-003-010',
            'title': 'Поиск по нескольким статусам',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Отправить GET /pet/findByStatus?status=available,pending'}
            ],
            'expected_result': 'Код ответа: 200 OK. Массив питомцев со статусами available или pending'
        },
        {
            'id': 'TC-003-011',
            'title': 'Поиск с несуществующими питомцами',
            'priority': 'Medium',
            'test_type': 'Positive',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен', 'Нет питомцев со статусом sold'],
            'steps': [
                {'step': 1, 'action': 'Отправить GET /pet/findByStatus?status=sold'}
            ],
            'expected_result': 'Код ответа: 200 OK. Пустой массив []'
        },
        {
            'id': 'TC-003-012',
            'title': 'Проверка сортировки по дате',
            'priority': 'Medium',
            'test_type': 'Positive',
            'technique': 'specification_based',
            'preconditions': ['API доступен', 'Есть несколько питомцев со статусом available'],
            'steps': [
                {'step': 1, 'action': 'Отправить GET /pet/findByStatus?status=available'},
                {'step': 2, 'action': 'Проверить порядок записей'}
            ],
            'expected_result': 'Питомцы отсортированы от новых к старым (по дате добавления)'
        }
    ]
    helper.add_test_cases_bulk(req_id, additional_tests)


def generate_req_004(helper: TestGeneratorHelper, req_id: str):
    """REQ-004: PUT /pet - Обновление питомца."""
    
    helper.add_analysis(
        req_id=req_id,
        inputs=['id', 'name', 'category', 'photoUrls', 'tags', 'status'],
        outputs=['200 OK', '404 Not Found', '409 Conflict'],
        business_rules=[
            'id обязательное для идентификации',
            'Все валидации как при создании',
            'Полное обновление (не PATCH)',
            'sold -> available запрещено (409)',
            'Логирование изменений'
        ],
        states=['available', 'pending', 'sold'],
        suggested_techniques=['state_transition', 'equivalence_partitioning']
    )
    
    tests = [
        {
            'id': 'TC-004-001',
            'title': 'Успешное обновление существующего питомца',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен', 'Питомец с id=123 существует'],
            'steps': [
                {'step': 1, 'action': 'Подготовить JSON с id=123 и обновленными данными'},
                {'step': 2, 'action': 'Отправить PUT /pet'}
            ],
            'expected_result': 'Код ответа: 200 OK. Питомец обновлен'
        },
        {
            'id': 'TC-004-002',
            'title': 'Обновление несуществующего питомца',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Подготовить JSON с id=999999'},
                {'step': 2, 'action': 'Отправить PUT /pet'}
            ],
            'expected_result': 'Код ответа: 404 Not Found'
        },
        {
            'id': 'TC-004-003',
            'title': 'Попытка изменить sold на available',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'state_transition',
            'preconditions': ['API доступен', 'Питомец с id=123 имеет status=sold'],
            'steps': [
                {'step': 1, 'action': 'Подготовить JSON с id=123 и status=available'},
                {'step': 2, 'action': 'Отправить PUT /pet'}
            ],
            'expected_result': 'Код ответа: 409 Conflict. Невозможно изменить sold на available'
        },
        {
            'id': 'TC-004-004',
            'title': 'Валидация при обновлении (некорректный name)',
            'priority': 'Medium',
            'test_type': 'Negative',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен', 'Питомец с id=123 существует'],
            'steps': [
                {'step': 1, 'action': 'Подготовить JSON с id=123 и name="A" (< 2 символов)'},
                {'step': 2, 'action': 'Отправить PUT /pet'}
            ],
            'expected_result': 'Код ответа: 400 Bad Request. Ошибка валидации name'
        }
    ]
    helper.add_test_cases_bulk(req_id, tests)


def generate_req_005(helper: TestGeneratorHelper, req_id: str):
    """REQ-005: POST /store/order - Размещение заказа."""
    
    helper.add_analysis(
        req_id=req_id,
        inputs=['id', 'petId', 'quantity', 'shipDate', 'status', 'complete'],
        outputs=['201 Created', '400 Bad Request', '404 Not Found'],
        business_rules=[
            'Заказ только на питомца в статусе available',
            'quantity: 1-100',
            'shipDate не в прошлом',
            'Атомарная проверка и создание',
            'Статус питомца меняется на pending',
            'Время обработки <= 2 сек'
        ],
        states=['placed', 'approved', 'delivered'],
        suggested_techniques=['boundary_value', 'equivalence_partitioning', 'state_transition']
    )
    
    # BVA для quantity
    qty_bva = create_boundary_test_cases(
        req_id=req_id,
        base_tc_id='TC-005',
        field_name='quantity',
        min_value=1,
        max_value=100,
        valid_example=50,
        invalid_low=0,
        invalid_high=101,
        endpoint='POST /store/order'
    )
    helper.add_test_cases_bulk(req_id, qty_bva)
    
    additional_tests = [
        {
            'id': 'TC-005-010',
            'title': 'Успешное создание заказа',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен', 'Питомец с petId=123 имеет status=available'],
            'steps': [
                {'step': 1, 'action': 'Подготовить JSON с petId=123, quantity=1'},
                {'step': 2, 'action': 'Отправить POST /store/order'}
            ],
            'expected_result': 'Код ответа: 201 Created. Заказ создан, статус питомца=pending'
        },
        {
            'id': 'TC-005-011',
            'title': 'Заказ на питомца не в статусе available',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'state_transition',
            'preconditions': ['API доступен', 'Питомец с petId=123 имеет status=sold'],
            'steps': [
                {'step': 1, 'action': 'Подготовить JSON с petId=123'},
                {'step': 2, 'action': 'Отправить POST /store/order'}
            ],
            'expected_result': 'Код ответа: 400 Bad Request. Питомец недоступен для заказа'
        },
        {
            'id': 'TC-005-012',
            'title': 'Заказ с несуществующим petId',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Подготовить JSON с petId=999999'},
                {'step': 2, 'action': 'Отправить POST /store/order'}
            ],
            'expected_result': 'Код ответа: 404 Not Found'
        },
        {
            'id': 'TC-005-013',
            'title': 'shipDate в прошлом',
            'priority': 'Medium',
            'test_type': 'Negative',
            'technique': 'error_guessing',
            'preconditions': ['API доступен', 'Питомец с petId=123 доступен'],
            'steps': [
                {'step': 1, 'action': 'Подготовить JSON с shipDate=2020-01-01T00:00:00Z'},
                {'step': 2, 'action': 'Отправить POST /store/order'}
            ],
            'expected_result': 'Код ответа: 400 Bad Request. Дата доставки не может быть в прошлом'
        }
    ]
    helper.add_test_cases_bulk(req_id, additional_tests)


def generate_req_006(helper: TestGeneratorHelper, req_id: str):
    """REQ-006: GET /store/order/{orderId} - Получение заказа."""
    
    helper.add_analysis(
        req_id=req_id,
        inputs=['orderId'],
        outputs=['200 OK', '400 Bad Request', '404 Not Found'],
        business_rules=[
            'orderId: 1-10 (ограничение демо)',
            'Идемпотентный метод',
            'Время ответа <= 500ms'
        ],
        suggested_techniques=['boundary_value', 'equivalence_partitioning']
    )
    
    # BVA для orderId (1-10)
    orderid_bva = create_boundary_test_cases(
        req_id=req_id,
        base_tc_id='TC-006',
        field_name='orderId',
        min_value=1,
        max_value=10,
        valid_example=5,
        invalid_low=0,
        invalid_high=11,
        endpoint='GET /store/order/{orderId}'
    )
    helper.add_test_cases_bulk(req_id, orderid_bva)
    
    additional_tests = [
        {
            'id': 'TC-006-010',
            'title': 'Получение существующего заказа',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен', 'Заказ с orderId=5 существует'],
            'steps': [
                {'step': 1, 'action': 'Отправить GET /store/order/5'}
            ],
            'expected_result': 'Код ответа: 200 OK. JSON с данными заказа'
        },
        {
            'id': 'TC-006-011',
            'title': 'Получение несуществующего заказа',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Отправить GET /store/order/8'}
            ],
            'expected_result': 'Код ответа: 404 Not Found'
        }
    ]
    helper.add_test_cases_bulk(req_id, additional_tests)


def generate_req_007(helper: TestGeneratorHelper, req_id: str):
    """REQ-007: DELETE /store/order/{orderId} - Удаление заказа."""
    
    helper.add_analysis(
        req_id=req_id,
        inputs=['orderId'],
        outputs=['204 No Content', '400 Bad Request', '404 Not Found'],
        business_rules=[
            'Можно удалить только placed/approved',
            'Delivered не удаляются',
            'Идемпотентная операция',
            'Статус питомца возвращается в available',
            'Атомарная транзакция',
            'Аудит-логирование'
        ],
        states=['placed', 'approved', 'delivered'],
        suggested_techniques=['state_transition', 'equivalence_partitioning']
    )
    
    tests = [
        {
            'id': 'TC-007-001',
            'title': 'Успешное удаление заказа в статусе placed',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен', 'Заказ с orderId=5 в статусе placed'],
            'steps': [
                {'step': 1, 'action': 'Отправить DELETE /store/order/5'}
            ],
            'expected_result': 'Код ответа: 204 No Content. Заказ удален, статус питомца=available'
        },
        {
            'id': 'TC-007-002',
            'title': 'Успешное удаление заказа в статусе approved',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен', 'Заказ с orderId=5 в статусе approved'],
            'steps': [
                {'step': 1, 'action': 'Отправить DELETE /store/order/5'}
            ],
            'expected_result': 'Код ответа: 204 No Content. Заказ удален'
        },
        {
            'id': 'TC-007-003',
            'title': 'Попытка удалить delivered заказ',
            'priority': 'High',
            'test_type': 'Negative',
            'technique': 'state_transition',
            'preconditions': ['API доступен', 'Заказ с orderId=5 в статусе delivered'],
            'steps': [
                {'step': 1, 'action': 'Отправить DELETE /store/order/5'}
            ],
            'expected_result': 'Код ответа: 400 Bad Request. Delivered заказы не могут быть удалены'
        },
        {
            'id': 'TC-007-004',
            'title': 'Удаление несуществующего заказа',
            'priority': 'Medium',
            'test_type': 'Negative',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Отправить DELETE /store/order/999'}
            ],
            'expected_result': 'Код ответа: 404 Not Found'
        },
        {
            'id': 'TC-007-005',
            'title': 'Идемпотентность: повторное удаление',
            'priority': 'Medium',
            'test_type': 'Positive',
            'technique': 'specification_based',
            'preconditions': ['API доступен', 'Заказ с orderId=5 уже удален'],
            'steps': [
                {'step': 1, 'action': 'Отправить DELETE /store/order/5 повторно'}
            ],
            'expected_result': 'Код ответа: 404 Not Found. Идемпотентное поведение'
        }
    ]
    helper.add_test_cases_bulk(req_id, tests)


def generate_basic_tests(helper: TestGeneratorHelper, req_id: str):
    """Генерация базового набора тестов для остальных требований."""
    
    # Простая эвристика: для каждого требования создаем минимум 3 теста
    helper.add_analysis(
        req_id=req_id,
        inputs=['various'],
        outputs=['2xx', '4xx'],
        business_rules=['Требуется детальный анализ'],
        suggested_techniques=['equivalence_partitioning', 'error_guessing']
    )
    
    tests = [
        {
            'id': f'{req_id.replace("REQ", "TC")}-001',
            'title': 'Успешный сценарий (happy path)',
            'priority': 'High',
            'test_type': 'Positive',
            'technique': 'equivalence_partitioning',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Выполнить операцию с валидными данными'}
            ],
            'expected_result': 'Операция выполнена успешно'
        },
        {
            'id': f'{req_id.replace("REQ", "TC")}-002',
            'title': 'Негативный сценарий: невалидные данные',
            'priority': 'Medium',
            'test_type': 'Negative',
            'technique': 'error_guessing',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Выполнить операцию с невалидными данными'}
            ],
            'expected_result': 'Код ответа: 400 Bad Request'
        },
        {
            'id': f'{req_id.replace("REQ", "TC")}-003',
            'title': 'Граничные условия',
            'priority': 'Medium',
            'test_type': 'Boundary',
            'technique': 'boundary_value',
            'preconditions': ['API доступен'],
            'steps': [
                {'step': 1, 'action': 'Проверить граничные значения полей'}
            ],
            'expected_result': 'Корректная обработка граничных значений'
        }
    ]
    helper.add_test_cases_bulk(req_id, tests)
    
    log_issue(f"ВНИМАНИЕ: {req_id} обработано базовым шаблоном. Рекомендуется детальная проработка.")


if __name__ == '__main__':
    main()
