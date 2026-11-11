"""FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from backend.app import __version__
from backend.app.api.routers import analytics, service
from backend.app.core.config import get_settings
from backend.app.services.context import DataNotLoadedError, FilterError

API_PREFIX = "/api/v1"

DESCRIPTION = """
Analytics API of **FINANCIAL INTELLIGENCE**, a financial intelligence and budget control
platform built on **synthetic data** of a fictional company.

**Global filters.** Every analytic endpoint accepts `start`, `end` (months, `YYYY-MM`),
`business_unit` (repeatable) and `compare`. Each response echoes the filters actually
applied in its `filters` field.

**Conventions.** Amounts are USD. Ratios are fractions (0.25 = 25%). `null` means the value
is not defined for the selection, for example a margin with no revenue or a comparison
whose period lies outside the available data.
"""

TAGS = [
    {"name": "Service", "description": "Service and data status"},
    {"name": "Catalogues", "description": "Dimensions and KPI definitions"},
    {"name": "Executive KPIs", "description": "Headline indicators"},
    {"name": "Time series", "description": "Monthly evolution"},
    {"name": "Budget vs actual", "description": "Budget comparisons and variances"},
    {"name": "Profitability", "description": "Revenue and margins by segment"},
    {"name": "Expenses", "description": "Operating expense breakdowns"},
    {"name": "Analysis", "description": "Contribution analysis, anomalies and insights"},
    {"name": "Records", "description": "Paginated analytical table"},
    {"name": "Exports", "description": "CSV downloads"},
    {"name": "Data quality", "description": "Pipeline runs and data-quality checks"},
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="FINANCIAL INTELLIGENCE API",
        description=DESCRIPTION,
        version=__version__,
        openapi_tags=TAGS,
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    @app.exception_handler(FilterError)
    async def invalid_filter(_: Request, error: FilterError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.exception_handler(DataNotLoadedError)
    async def data_not_loaded(_: Request, error: DataNotLoadedError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(error)}
        )

    @app.exception_handler(OperationalError)
    async def database_unavailable(_: Request, __: OperationalError) -> JSONResponse:
        # Never leak connection details (host, user) to the client.
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "The database is unavailable."},
        )

    app.include_router(service.router, prefix=API_PREFIX)
    app.include_router(analytics.router, prefix=API_PREFIX)
    return app


app = create_app()
