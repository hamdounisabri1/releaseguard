"""The ``/api/v1`` router. Each area gets its own module in this package (``auth.py``,
``applications.py``, ``deployments.py``, …) and is included here as it is built.
"""

from fastapi import APIRouter

from app.api.v1 import auth

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
