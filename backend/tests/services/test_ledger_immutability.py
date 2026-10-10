import re
from pathlib import Path

from fastapi.routing import APIRoute

from app.main import app
from app.repositories import inventory as inventory_repo
from app.services import inventory as inventory_service

APP_DIR = Path(__file__).resolve().parents[2] / "app"

MUTATION_PATTERNS = (
    re.compile(r"update\(\s*StockMovement\b"),
    re.compile(r"delete\(\s*StockMovement\b"),
    re.compile(r"UPDATE\s+stock_movements", re.IGNORECASE),
    re.compile(r"DELETE\s+FROM\s+stock_movements", re.IGNORECASE),
)


def test_no_code_updates_or_deletes_ledger_rows() -> None:
    offenders: list[str] = []
    for path in APP_DIR.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for pattern in MUTATION_PATTERNS:
            if pattern.search(source):
                offenders.append(f"{path.relative_to(APP_DIR)}: {pattern.pattern}")
    assert offenders == []


def test_ledger_modules_expose_no_update_or_delete_functions() -> None:
    for module in (inventory_repo, inventory_service):
        names = [name for name in dir(module) if not name.startswith("_")]
        assert not [name for name in names if name.startswith(("update", "delete", "edit"))]


def test_api_has_no_mutation_route_for_movements() -> None:
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if "/inventory/movements" not in route.path and "/inventory/sales" not in route.path:
            continue
        assert route.methods <= {"GET", "POST"}, f"{route.path} allows {route.methods}"
