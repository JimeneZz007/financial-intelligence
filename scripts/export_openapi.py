"""Writes the OpenAPI schema of the API to a file (default: frontend/openapi.json).

The frontend generates its TypeScript types from this file (`npm run gen:api`), so the
client can never drift from the contract the server actually implements.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from backend.app.main import app

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"


def main() -> None:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PATH
    target.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"OpenAPI schema written to {target}")


if __name__ == "__main__":
    main()
