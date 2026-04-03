"""
Тесты безопасности загрузки изображений (шаг 1 визарда).
"""
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-0000000000000000")

import tempfile
from pathlib import Path

import pytest


def test_path_traversal_filename_blocked(tmp_path):
    """
    Файл с именем вида '../../secret.txt' не должен записываться
    за пределы upload_dir. Path(filename).name отрезает директории,
    а resolve check блокирует любой оставшийся выход за границу.
    """
    upload_dir = tmp_path / "uploads" / "1"
    upload_dir.mkdir(parents=True)

    malicious_filename = "../../secret.txt"
    safe_name = Path(malicious_filename).name  # → "secret.txt"

    assert safe_name == "secret.txt", "Path.name должен отрезать директории"

    dest = upload_dir / safe_name
    assert dest.resolve().is_relative_to(upload_dir.resolve()), \
        "После санирования путь должен оставаться внутри upload_dir"

    # Убеждаемся, что оригинальный (несанированный) путь выходит за пределы
    raw_dest = upload_dir / malicious_filename
    assert not raw_dest.resolve().is_relative_to(upload_dir.resolve()), \
        "Несанированный путь должен выходить за пределы upload_dir"


def test_dotdot_name_blocked_by_resolve_check(tmp_path):
    """
    Имя файла '../' после Path.name даёт '..'. Такое имя не является пустым,
    но resolve check блокирует запись за пределы upload_dir.
    """
    upload_dir = tmp_path / "uploads" / "1"
    upload_dir.mkdir(parents=True)

    filename = "../"
    safe_name = Path(filename).name   # → '..'
    assert safe_name == ".."

    # Пустая проверка safe_name не сработает, но resolve check должен заблокировать
    dest = upload_dir / safe_name
    assert not dest.resolve().is_relative_to(upload_dir.resolve()), \
        "Путь upload_dir/..' должен выходить за пределы upload_dir"


def test_normal_filename_passes(tmp_path):
    """Обычное имя файла проходит все проверки и остаётся в upload_dir."""
    upload_dir = tmp_path / "uploads" / "1"
    upload_dir.mkdir(parents=True)

    filename = "photo.jpg"
    safe_name = Path(filename).name
    assert safe_name == "photo.jpg"

    dest = upload_dir / safe_name
    assert dest.resolve().is_relative_to(upload_dir.resolve())
