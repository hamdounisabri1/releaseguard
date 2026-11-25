"""The ``/api/v1`` router. Each area gets its own module in this package (``auth.py``,
``applications.py``, ``deployments.py``, …) and is included here as it is built.
"""

from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")
