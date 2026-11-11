"""Shared request dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from backend.app.analytics.periods import ComparisonMode
from backend.app.db.session import get_session
from backend.app.services.context import AnalysisContext, build_context

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"

SessionDep = Annotated[Session, Depends(get_session)]


def analysis_context(
    session: SessionDep,
    start: Annotated[
        str | None,
        Query(
            pattern=MONTH_PATTERN,
            description="First month of the period (YYYY-MM). Default: 12 months ending at `end`.",
            examples=["2025-01"],
        ),
    ] = None,
    end: Annotated[
        str | None,
        Query(
            pattern=MONTH_PATTERN,
            description="Last month of the period (YYYY-MM). Default: latest month with data.",
            examples=["2025-12"],
        ),
    ] = None,
    business_unit: Annotated[
        list[str] | None,
        Query(
            description="Business unit code. Repeat the parameter to select several. "
            "Default: all units.",
            examples=["RET"],
        ),
    ] = None,
    compare: Annotated[
        ComparisonMode,
        Query(
            description="Comparison basis: same months one year earlier, or the equally long "
            "period immediately before."
        ),
    ] = "previous_year",
) -> AnalysisContext:
    """Global filters shared by every analytic endpoint."""
    return build_context(session, start, end, business_unit, compare)


ContextDep = Annotated[AnalysisContext, Depends(analysis_context)]
