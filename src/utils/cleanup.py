#!/usr/bin/env python3
"""
Скрипт очистки для AI Test Generator.

Удаляет state файлы, временные файлы и опционально экспортированные результаты.
Подготавливает проект к новым генерациям.
"""
import argparse
import sys
from pathlib import Path
from datetime import datetime

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class Cleanup:
    """Утилита очистки проекта."""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent
        self.deleted_files = []
        self.deleted_dirs = []
        self.artifacts_dir = self.project_root / "artifacts"

    def get_state_files(self) -> list[Path]:
        """Возвращает список state файлов."""
        patterns = [
            ".test_generator_state.json",
            ".test_generator_state.*.json",
        ]
        files = []
        for pattern in patterns:
            files.extend(self.project_root.glob(pattern))
        return files

    def get_log_files(self) -> list[Path]:
        """Возвращает список лог файлов."""
        log_dir = self.project_root / "logs"
        if log_dir.exists():
            return list(log_dir.glob("*.log"))
        return []

    def get_cache_dirs(self) -> list[Path]:
        """Возвращает список кэш директорий (исключая venv)."""
        patterns = [
            "__pycache__",
            ".pytest_cache",
            "*.egg-info",
            ".mypy_cache",
            ".ruff_cache",
        ]
        exclude = {"venv", ".venv", "node_modules", ".git"}
        dirs = []
        for pattern in patterns:
            for d in self.project_root.rglob(pattern):
                # Исключаем директории внутри venv и подобных
                if not any(part in exclude for part in d.parts):
                    dirs.append(d)
        return [d for d in dirs if d.is_dir()]

    def get_export_files(self) -> list[Path]:
        """Возвращает список экспортированных файлов в корне проекта."""
        patterns = [
            "test_cases*.xlsx",
            "test_cases*.csv",
            "tests*.xlsx",
            "tests*.csv",
        ]
        files = []
        for pattern in patterns:
            files.extend(self.project_root.glob(pattern))
        return files

    def get_artifacts_files(self) -> list[Path]:
        """Возвращает список файлов в директории artifacts."""
        if self.artifacts_dir.exists():
            return [f for f in self.artifacts_dir.iterdir() if f.is_file()]
        return []

    def get_temp_files(self) -> list[Path]:
        """Возвращает список временных файлов (исключая venv)."""
        patterns = [
            "*.pyc",
            ".DS_Store",
            "Thumbs.db",
            "*.tmp",
            "*~",
        ]
        exclude = {"venv", ".venv", "node_modules", ".git"}
        files = []
        for pattern in patterns:
            for f in self.project_root.rglob(pattern):
                if not any(part in exclude for part in f.parts):
                    files.append(f)
        return [f for f in files if f.is_file()]

    def clean_state(self, dry_run: bool = False) -> int:
        """Удаляет state файлы."""
        files = self.get_state_files()
        return self._delete_files(files, "state", dry_run)

    def clean_logs(self, dry_run: bool = False) -> int:
        """Удаляет лог файлы."""
        files = self.get_log_files()
        return self._delete_files(files, "logs", dry_run)

    def clean_cache(self, dry_run: bool = False) -> int:
        """Удаляет кэш директории."""
        dirs = self.get_cache_dirs()
        return self._delete_dirs(dirs, "cache", dry_run)

    def clean_exports(self, dry_run: bool = False) -> int:
        """Удаляет экспортированные файлы в корне проекта."""
        files = self.get_export_files()
        return self._delete_files(files, "exports", dry_run)

    def clean_artifacts(self, dry_run: bool = False) -> int:
        """Удаляет файлы из директории artifacts."""
        files = self.get_artifacts_files()
        return self._delete_files(files, "artifacts", dry_run)

    def clean_temp(self, dry_run: bool = False) -> int:
        """Удаляет временные файлы."""
        files = self.get_temp_files()
        return self._delete_files(files, "temp", dry_run)

    def backup_artifacts(self, dry_run: bool = False) -> bool:
        """
        Создает бэкап директории artifacts с timestamp.
        
        Returns:
            True если бэкап создан или не требуется
        """
        if not self.artifacts_dir.exists() or not any(self.artifacts_dir.iterdir()):
            logger.info("Директория artifacts пуста, бэкап не требуется")
            return True
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.project_root / f"artifacts_backup_{timestamp}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] Будет создан бэкап: {backup_dir}")
            return True
        
        try:
            import shutil
            shutil.copytree(self.artifacts_dir, backup_dir)
            logger.info(f"Создан бэкап: {backup_dir}")
            return True
        except Exception as e:
            logger.error(f"Ошибка создания бэкапа: {e}")
            return False

    def prepare_for_new_generation(self, dry_run: bool = False, backup: bool = True) -> dict:
        """
        Подготавливает проект к новой генерации тестов.
        
        Удаляет:
        - State файлы
        - Кэш директории
        - Временные файлы
        - Файлы в artifacts (с опциональным бэкапом)
        
        Args:
            dry_run: Только показать что будет удалено
            backup: Создать бэкап artifacts перед очисткой
        
        Returns:
            Словарь с количеством удаленных элементов
        """
        results = {}
        
        # Создать бэкап artifacts если нужно
        if backup and not dry_run:
            backup_created = self.backup_artifacts(dry_run)
            if not backup_created:
                logger.warning("Не удалось создать бэкап, пропускаем очистку artifacts")
                results["backup"] = 0
            else:
                results["backup"] = 1
        
        # Очистка state (обязательно)
        results["state"] = self.clean_state(dry_run)
        
        # Очистка artifacts (если есть бэкап или бэкап не требуется)
        if not backup or results.get("backup", 0) > 0 or dry_run:
            results["artifacts"] = self.clean_artifacts(dry_run)
        
        # Очистка кэша и временных файлов
        results["cache"] = self.clean_cache(dry_run)
        results["temp"] = self.clean_temp(dry_run)
        
        return results

    def clean_all(self, dry_run: bool = False, include_exports: bool = False) -> dict:
        """
        Полная очистка.

        Args:
            dry_run: Только показать что будет удалено
            include_exports: Включить экспортированные файлы

        Returns:
            Словарь с количеством удаленных элементов по категориям
        """
        results = {
            "state": self.clean_state(dry_run),
            "logs": self.clean_logs(dry_run),
            "cache": self.clean_cache(dry_run),
            "temp": self.clean_temp(dry_run),
        }

        if include_exports:
            results["exports"] = self.clean_exports(dry_run)
            results["artifacts"] = self.clean_artifacts(dry_run)

        return results

    def _delete_files(self, files: list[Path], category: str, dry_run: bool) -> int:
        """Удаляет список файлов."""
        count = 0
        for f in files:
            if dry_run:
                logger.info(f"[DRY-RUN] Будет удален ({category}): {f}")
            else:
                try:
                    f.unlink()
                    logger.info(f"Удален ({category}): {f}")
                    self.deleted_files.append(f)
                    count += 1
                except Exception as e:
                    logger.error(f"Ошибка удаления {f}: {e}")
        return count if not dry_run else len(files)

    def _delete_dirs(self, dirs: list[Path], category: str, dry_run: bool) -> int:
        """Удаляет список директорий."""
        import shutil
        count = 0
        for d in dirs:
            if dry_run:
                logger.info(f"[DRY-RUN] Будет удалена ({category}): {d}")
            else:
                try:
                    shutil.rmtree(d)
                    logger.info(f"Удалена ({category}): {d}")
                    self.deleted_dirs.append(d)
                    count += 1
                except Exception as e:
                    logger.error(f"Ошибка удаления {d}: {e}")
        return count if not dry_run else len(dirs)

    def print_summary(self, results: dict, dry_run: bool):
        """Выводит итоги очистки."""
        total = sum(v for k, v in results.items() if k != "backup")
        action = "Будет удалено" if dry_run else "Удалено"

        print()
        print("=" * 50)
        print(f"{'ПРЕДПРОСМОТР' if dry_run else 'ОЧИСТКА ЗАВЕРШЕНА'}")
        print("=" * 50)

        if "backup" in results and results["backup"] > 0:
            print(f"  {'✓' if not dry_run else '→'} Бэкап artifacts создан")

        for category, count in results.items():
            if category != "backup" and count > 0:
                print(f"  {category}: {count}")

        print("-" * 50)
        print(f"  {action} всего: {total}")
        print("=" * 50)
        
        if not dry_run:
            print()
            print("Проект готов к новой генерации тестов!")
            print("Используйте: ./venv/bin/python main.py load-demo -n petstore")


def main():
    parser = argparse.ArgumentParser(
        description="Очистка временных файлов AI Test Generator"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Включить экспортированные файлы (xlsx, csv)"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Только показать что будет удалено"
    )
    parser.add_argument(
        "--state-only", "-s",
        action="store_true",
        help="Удалить только state файлы"
    )
    parser.add_argument(
        "--cache-only", "-c",
        action="store_true",
        help="Удалить только кэш (__pycache__ и т.д.)"
    )
    parser.add_argument(
        "--prepare", "-p",
        action="store_true",
        help="Подготовить проект к новой генерации (state + artifacts + cache + temp)"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Не создавать бэкап artifacts при подготовке"
    )

    args = parser.parse_args()

    cleanup = Cleanup()

    if args.state_only:
        count = cleanup.clean_state(args.dry_run)
        action = "Будет удалено" if args.dry_run else "Удалено"
        print(f"{action} state файлов: {count}")
    elif args.cache_only:
        count = cleanup.clean_cache(args.dry_run)
        action = "Будет удалено" if args.dry_run else "Удалено"
        print(f"{action} кэш директорий: {count}")
    elif args.prepare:
        results = cleanup.prepare_for_new_generation(
            dry_run=args.dry_run,
            backup=not args.no_backup
        )
        cleanup.print_summary(results, args.dry_run)
    else:
        results = cleanup.clean_all(
            dry_run=args.dry_run,
            include_exports=args.all
        )
        cleanup.print_summary(results, args.dry_run)


if __name__ == "__main__":
    main()