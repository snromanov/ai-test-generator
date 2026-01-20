#!/usr/bin/env python3
"""
Универсальный скрипт генерации тест-кейсов из требований.

Обёртка над командой `python main.py generate` для удобства запуска.

Использование:
    ./generate_tests.py                          # Из requirements/raw
    ./generate_tests.py --source demo/petstore   # Из демо
    ./generate_tests.py --source my_reqs.md      # Из файла
    ./generate_tests.py --help                   # Помощь
"""
import sys
import subprocess
from pathlib import Path


def main():
    """Запускает команду generate с переданными аргументами."""
    
    # Путь к main.py
    project_root = Path(__file__).parent
    main_py = project_root / "main.py"
    
    # Путь к python в venv
    venv_python = project_root / "venv" / "bin" / "python"
    if not venv_python.exists():
        venv_python = project_root / "venv" / "Scripts" / "python.exe"  # Windows
    
    # Используем системный python если venv не найден
    python_cmd = str(venv_python) if venv_python.exists() else "python3"
    
    # Собираем команду
    cmd = [python_cmd, str(main_py), "generate"] + sys.argv[1:]
    
    # Запускаем
    try:
        result = subprocess.run(cmd, check=False)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n\nГенерация прервана пользователем")
        sys.exit(1)
    except Exception as e:
        print(f"Ошибка запуска: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
