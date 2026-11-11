"""Service status, catalogues and data quality."""

from __future__ import annotations

from fastapi import APIRouter, Response, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.app import __version__
from backend.app.analytics.periods import month_key
from backend.app.api.deps import SessionDep
from backend.app.core.kpi_catalog import KPI_CATALOG
from backend.app.repositories import warehouse
from backend.app.schemas import (
    AvailablePeriod,
    DataQualityResponse,
    DataStatus,
    DimensionsResponse,
    HealthResponse,
    KpiCatalogResponse,
)
from backend.app.services.context import DataNotLoadedError
from backend.app.services.quality import data_quality_report

router = APIRouter()

COMPANY_NAME = "Grupo Comercial Altamira"
CURRENCY = "USD"


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["Service"],
    summary="Service and data status",
    responses={503: {"model": HealthResponse, "description": "Database unreachable"}},
)
def health(session: SessionDep, response: Response) -> HealthResponse:
    """Reports whether the API can reach the database and when data was last loaded."""
    try:
        session.execute(text("SELECT 1"))
        period = warehouse.available_period(session)
        run = warehouse.latest_successful_run(session)
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(
            status="degraded", database="down", version=__version__, data=DataStatus(loaded=False)
        )
    return HealthResponse(
        status="ok",
        database="up",
        version=__version__,
        data=DataStatus(
            loaded=period is not None,
            last_successful_run_at=run["finished_at"] if run else None,
            period_start=month_key(period.start) if period else None,
            period_end=month_key(period.end) if period else None,
        ),
    )


@router.get(
    "/dimensions",
    response_model=DimensionsResponse,
    tags=["Catalogues"],
    summary="Dimension catalogue and available period",
)
def dimensions(session: SessionDep) -> DimensionsResponse:
    """Everything a client needs to build filters: units, categories, accounts and period."""
    period = warehouse.available_period(session)
    if period is None:
        raise DataNotLoadedError("The warehouse is empty. Run the ETL pipeline first.")
    months = [month_key(month) for month in period.months]
    return DimensionsResponse(
        currency=CURRENCY,
        company=COMPANY_NAME,
        synthetic=True,
        period=AvailablePeriod(
            start=months[0],
            end=months[-1],
            months=months,
            fiscal_years=sorted({int(month[:4]) for month in months}),
        ),
        business_units=warehouse.business_units(session),
        categories=warehouse.categories(session),
        products=warehouse.products(session),
        cost_centers=warehouse.cost_centers(session),
        accounts=warehouse.accounts(session),
    )


@router.get(
    "/kpi-catalog",
    response_model=KpiCatalogResponse,
    tags=["Catalogues"],
    summary="Formal KPI definitions",
)
def kpi_catalog() -> KpiCatalogResponse:
    """Formula, unit, grain, filters, null handling and limitations of every KPI."""
    return KpiCatalogResponse(kpis=list(KPI_CATALOG))


@router.get(
    "/data-quality",
    response_model=DataQualityResponse,
    tags=["Data quality"],
    summary="Latest pipeline run, row accounting and data-quality checks",
)
def data_quality(session: SessionDep) -> DataQualityResponse:
    return data_quality_report(session)
