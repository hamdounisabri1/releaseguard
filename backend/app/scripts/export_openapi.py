"""Print the API's OpenAPI document: ``uv run python -m app.scripts.export_openapi [out.json]``.

The same document ``/openapi.json`` serves, without a running server or a database (the engine
is lazy). CI uses it to check that ``frontend/types/api.ts`` matches the backend; locally,
``pnpm api:types`` reads it from the running backend instead.
"""

import json
import sys
from pathlib import Path

from app.main import create_app


def render() -> str:
    return json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str]) -> None:
    document = render()
    if argv:
        Path(argv[0]).write_text(document, encoding="utf-8")
    else:
        sys.stdout.write(document)


if __name__ == "__main__":
    main(sys.argv[1:])
