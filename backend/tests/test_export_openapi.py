"""The OpenAPI export that frontend/types/api.ts is generated from (SCRUM-27)."""

import json
from pathlib import Path

from app.scripts.export_openapi import main, render


def test_export_matches_the_served_document_and_is_stable() -> None:
    document = json.loads(render())

    assert "/api/v1/auth/me" in document["paths"]
    assert "ErrorResponse" in document["components"]["schemas"]
    assert render() == render()  # sorted keys: the generated types diff cleanly


def test_export_writes_to_a_file(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"

    main([str(out)])

    assert json.loads(out.read_text(encoding="utf-8"))["info"]["title"] == "ReleaseGuard API"
