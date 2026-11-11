"""Master data and business assumptions of the synthetic company.

Everything that shapes the dataset lives here as explicit, named constants so the
assumptions documented in docs/DATA_GENERATION.md can be traced to code.
All monetary values are in USD.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

SEED = 20230101
GENERATOR_VERSION = "1.0.0"
COMPANY_NAME = "Grupo Comercial Altamira"
CURRENCY = "USD"
PERIOD_START = date(2023, 1, 1)
PERIOD_END = date(2025, 12, 31)


# --------------------------------------------------------------------------- #
# Business units
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BusinessUnit:
    code: str
    name: str
    channel: str
    base_annual_revenue: float  # expected net revenue in the base year (2023)
    annual_growth: float  # expected nominal growth rate
    price_factor: float  # realised price as a fraction of list price
    base_discount_rate: float
    weekday_profile: tuple[float, ...]  # Monday..Sunday relative demand
    category_mix: dict[str, float]  # share of the unit's revenue by category
    headcount_growth: float  # annual growth of the payroll base
    budget_stretch: float  # planning optimism applied to revenue targets


BUSINESS_UNITS: tuple[BusinessUnit, ...] = (
    BusinessUnit(
        code="RET",
        name="Retail Stores",
        channel="Physical stores",
        base_annual_revenue=19_500_000,
        annual_growth=0.03,
        price_factor=1.00,
        base_discount_rate=0.035,
        weekday_profile=(0.85, 0.85, 0.90, 0.95, 1.15, 1.40, 1.20),
        category_mix={"ELE": 0.30, "OFF": 0.12, "FUR": 0.18, "HOM": 0.25, "ACC": 0.15},
        headcount_growth=0.00,
        budget_stretch=1.020,
    ),
    BusinessUnit(
        code="ECM",
        name="E-commerce",
        channel="Online",
        base_annual_revenue=9_000_000,
        annual_growth=0.21,
        price_factor=0.97,
        base_discount_rate=0.060,
        weekday_profile=(1.05, 1.00, 1.00, 1.00, 0.95, 0.95, 1.10),
        category_mix={"ELE": 0.40, "OFF": 0.10, "FUR": 0.10, "HOM": 0.20, "ACC": 0.20},
        headcount_growth=0.08,
        budget_stretch=1.030,
    ),
    BusinessUnit(
        code="WHS",
        name="Wholesale Distribution",
        channel="Distributors",
        base_annual_revenue=14_000_000,
        annual_growth=0.06,
        price_factor=0.80,
        base_discount_rate=0.020,
        weekday_profile=(1.20, 1.25, 1.20, 1.15, 1.00, 0.20, 0.00),
        category_mix={"ELE": 0.35, "OFF": 0.30, "FUR": 0.10, "HOM": 0.20, "ACC": 0.05},
        headcount_growth=0.01,
        budget_stretch=1.015,
    ),
    BusinessUnit(
        code="COR",
        name="Corporate Solutions",
        channel="B2B contracts",
        base_annual_revenue=6_500_000,
        annual_growth=0.09,
        price_factor=0.88,
        base_discount_rate=0.040,
        weekday_profile=(1.15, 1.20, 1.20, 1.15, 1.05, 0.00, 0.00),
        category_mix={"ELE": 0.30, "OFF": 0.35, "FUR": 0.28, "HOM": 0.02, "ACC": 0.05},
        headcount_growth=0.03,
        budget_stretch=1.020,
    ),
)
BU_CODES: tuple[str, ...] = tuple(bu.code for bu in BUSINESS_UNITS)


# --------------------------------------------------------------------------- #
# Product categories and products
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Category:
    code: str
    name: str
    standard_margin: float  # gross margin at list price
    seasonality: tuple[float, ...]  # January..December relative demand


CATEGORIES: tuple[Category, ...] = (
    Category(
        "ELE",
        "Electronics",
        0.28,
        (0.85, 0.82, 0.90, 0.92, 0.95, 1.00, 1.00, 0.98, 0.95, 1.00, 1.35, 1.28),
    ),
    Category(
        "OFF",
        "Office Supplies",
        0.46,
        (1.15, 1.10, 1.00, 0.97, 0.95, 0.92, 0.98, 1.12, 1.05, 1.00, 0.96, 0.80),
    ),
    Category(
        "FUR",
        "Furniture",
        0.40,
        (0.92, 0.90, 0.98, 1.02, 1.05, 1.08, 1.10, 1.05, 1.00, 0.98, 0.98, 0.94),
    ),
    Category(
        "HOM",
        "Home & Kitchen",
        0.44,
        (0.86, 0.84, 0.92, 0.95, 1.10, 0.98, 0.95, 0.94, 0.95, 1.00, 1.18, 1.33),
    ),
    Category(
        "ACC",
        "Accessories",
        0.56,
        (0.88, 0.86, 0.92, 0.94, 0.98, 0.98, 1.00, 1.02, 0.97, 1.00, 1.20, 1.25),
    ),
)
CATEGORY_BY_CODE: dict[str, Category] = {c.code: c for c in CATEGORIES}


@dataclass(frozen=True)
class Product:
    code: str
    name: str
    category_code: str
    list_price: float  # base-year list price
    category_weight: float  # share of the category revenue


PRODUCTS: tuple[Product, ...] = (
    Product("ELE-001", 'Business Laptop 14"', "ELE", 899.00, 0.26),
    Product("ELE-002", 'QHD Monitor 27"', "ELE", 329.00, 0.17),
    Product("ELE-003", "Wireless Headphones", "ELE", 129.00, 0.14),
    Product("ELE-004", 'Tablet 10"', "ELE", 449.00, 0.18),
    Product("ELE-005", "Laser Printer", "ELE", 249.00, 0.13),
    Product("ELE-006", "Wi-Fi 6 Router", "ELE", 119.00, 0.12),
    Product("OFF-001", "Copy Paper Box (10 reams)", "OFF", 48.00, 0.30),
    Product("OFF-002", "Toner Cartridge", "OFF", 79.00, 0.24),
    Product("OFF-003", "Ballpoint Pens (50 pack)", "OFF", 14.50, 0.10),
    Product("OFF-004", "Ring Binders (12 pack)", "OFF", 32.00, 0.10),
    Product("OFF-005", "Whiteboard 120x90 cm", "OFF", 89.00, 0.12),
    Product("OFF-006", "Desk Organizer Set", "OFF", 27.00, 0.14),
    Product("FUR-001", "Ergonomic Office Chair", "FUR", 289.00, 0.28),
    Product("FUR-002", "Height-Adjustable Desk", "FUR", 549.00, 0.24),
    Product("FUR-003", "4-Drawer Filing Cabinet", "FUR", 219.00, 0.12),
    Product("FUR-004", "5-Tier Bookshelf", "FUR", 139.00, 0.12),
    Product("FUR-005", "8-Seat Conference Table", "FUR", 1190.00, 0.12),
    Product("FUR-006", "3-Seat Lounge Sofa", "FUR", 799.00, 0.12),
    Product("HOM-001", "Espresso Machine", "HOM", 349.00, 0.20),
    Product("HOM-002", "Air Fryer 5 L", "HOM", 119.00, 0.22),
    Product("HOM-003", "Cookware Set (10 pieces)", "HOM", 159.00, 0.16),
    Product("HOM-004", "Robot Vacuum", "HOM", 279.00, 0.18),
    Product("HOM-005", "Queen Bedding Set", "HOM", 89.00, 0.12),
    Product("HOM-006", "Blender 1.5 L", "HOM", 69.00, 0.12),
    Product("ACC-001", "Laptop Backpack", "ACC", 59.00, 0.22),
    Product("ACC-002", "USB-C Hub 7-in-1", "ACC", 45.00, 0.20),
    Product("ACC-003", "Wireless Mouse", "ACC", 29.00, 0.18),
    Product("ACC-004", "Mechanical Keyboard", "ACC", 89.00, 0.16),
    Product("ACC-005", "Premium Phone Case", "ACC", 24.00, 0.12),
    Product("ACC-006", "Power Bank 20,000 mAh", "ACC", 39.00, 0.12),
)

# Maximum deviation of a product's margin around its category standard margin.
PRODUCT_MARGIN_SPREAD = 0.04

# Annual list-price and supplier-cost adjustments applied every January 1st.
PRICE_INCREASE_BY_YEAR: dict[int, float] = {2023: 0.0, 2024: 0.030, 2025: 0.035}
COST_INFLATION_BY_YEAR: dict[int, float] = {2023: 0.0, 2024: 0.032, 2025: 0.030}

# Additional discount (percentage points) granted in promotional months.
PROMO_DISCOUNT: dict[int, dict[str, float]] = {
    1: {"RET": 0.03, "ECM": 0.03, "WHS": 0.00, "COR": 0.00},
    11: {"RET": 0.06, "ECM": 0.06, "WHS": 0.02, "COR": 0.02},
}

# Demand noise (standard deviation of log-normal multipliers).
NOISE_ROW = 0.12  # date x unit x product
NOISE_DAY_UNIT = 0.06  # shared by all products of a unit on a given day
NOISE_MONTH_UNIT_CATEGORY = 0.035  # shared within a unit-category-month
NOISE_DISCOUNT_RATE = 0.008  # absolute, on the discount rate


# --------------------------------------------------------------------------- #
# Cost centres and chart of accounts
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CostCenter:
    code: str
    name: str
    function_area: str


COST_CENTERS: tuple[CostCenter, ...] = (
    CostCenter("SAL", "Sales & Commercial", "Commercial"),
    CostCenter("MKT", "Marketing", "Commercial"),
    CostCenter("LOG", "Logistics & Operations", "Operations"),
    CostCenter("ADM", "Administration & Finance", "Support"),
    CostCenter("TEC", "Technology", "Support"),
    CostCenter("HRS", "People & Culture", "Support"),
)


@dataclass(frozen=True)
class Account:
    code: str
    name: str
    account_type: str  # REVENUE | DIRECT_COST | OPERATING_EXPENSE
    account_group: str
    cost_behavior: str  # VARIABLE | FIXED | SEMI_VARIABLE | DISCRETIONARY | NOT_APPLICABLE
    statement_order: int


REVENUE_ACCOUNT = "4000"
COGS_ACCOUNT = "5000"

ACCOUNTS: tuple[Account, ...] = (
    Account(REVENUE_ACCOUNT, "Net Sales Revenue", "REVENUE", "Revenue", "NOT_APPLICABLE", 10),
    Account(COGS_ACCOUNT, "Cost of Goods Sold", "DIRECT_COST", "Cost of Sales", "VARIABLE", 20),
    Account("6100", "Salaries & Wages", "OPERATING_EXPENSE", "Personnel", "FIXED", 30),
    Account("6150", "Employee Benefits", "OPERATING_EXPENSE", "Personnel", "FIXED", 40),
    Account(
        "6200", "Advertising & Promotion", "OPERATING_EXPENSE", "Marketing", "DISCRETIONARY", 50
    ),
    Account("6300", "Rent & Occupancy", "OPERATING_EXPENSE", "Occupancy", "FIXED", 60),
    Account("6350", "Utilities", "OPERATING_EXPENSE", "Occupancy", "SEMI_VARIABLE", 70),
    Account("6400", "Freight & Distribution", "OPERATING_EXPENSE", "Logistics", "VARIABLE", 80),
    Account("6500", "Software & IT Services", "OPERATING_EXPENSE", "Technology", "FIXED", 90),
    Account(
        "6600",
        "Professional Services",
        "OPERATING_EXPENSE",
        "General & Administrative",
        "DISCRETIONARY",
        100,
    ),
    Account(
        "6700",
        "Travel & Entertainment",
        "OPERATING_EXPENSE",
        "General & Administrative",
        "DISCRETIONARY",
        110,
    ),
    Account("6800", "Payment Processing Fees", "OPERATING_EXPENSE", "Selling", "VARIABLE", 120),
    Account(
        "6900", "Depreciation & Amortization", "OPERATING_EXPENSE", "Depreciation", "FIXED", 130
    ),
)
OPEX_ACCOUNT_CODES: tuple[str, ...] = tuple(
    a.code for a in ACCOUNTS if a.account_type == "OPERATING_EXPENSE"
)


# --------------------------------------------------------------------------- #
# Operating expense assumptions
# --------------------------------------------------------------------------- #
# Base-year annual amount for fixed / discretionary accounts, by business unit.
OPEX_BASE_ANNUAL: dict[str, dict[str, float]] = {
    "6100": {"RET": 2_750_000, "ECM": 720_000, "WHS": 760_000, "COR": 640_000},
    "6300": {"RET": 1_050_000, "ECM": 96_000, "WHS": 150_000, "COR": 72_000},
    "6350": {"RET": 215_000, "ECM": 30_000, "WHS": 48_000, "COR": 20_000},
    "6500": {"RET": 130_000, "ECM": 180_000, "WHS": 60_000, "COR": 66_000},
    "6600": {"RET": 95_000, "ECM": 60_000, "WHS": 55_000, "COR": 70_000},
    "6700": {"RET": 50_000, "ECM": 24_000, "WHS": 78_000, "COR": 96_000},
    "6900": {"RET": 260_000, "ECM": 110_000, "WHS": 95_000, "COR": 40_000},
}

# Accounts driven by revenue: expense = rate x net revenue of the month.
OPEX_REVENUE_RATE: dict[str, dict[str, float]] = {
    "6200": {"RET": 0.023, "ECM": 0.060, "WHS": 0.006, "COR": 0.012},
    "6400": {"RET": 0.011, "ECM": 0.050, "WHS": 0.029, "COR": 0.019},
    "6800": {"RET": 0.017, "ECM": 0.029, "WHS": 0.0035, "COR": 0.004},
}

BENEFITS_RATE = 0.22  # employee benefits as a fraction of salaries
SALARY_RAISE_BY_YEAR: dict[int, float] = {2023: 0.0, 2024: 0.040, 2025: 0.045}
RENT_ESCALATION = 0.035
SOFTWARE_ESCALATION = 0.05
UTILITIES_INFLATION = 0.04
DEPRECIATION_STEP = 0.04

# January..December indices (mean 1.0 is enforced in code).
ADVERTISING_CALENDAR = (0.80, 0.85, 0.95, 0.95, 1.10, 0.95, 0.95, 0.95, 0.95, 1.05, 1.40, 1.10)
UTILITIES_CALENDAR = (0.95, 0.92, 0.95, 0.98, 1.00, 1.05, 1.10, 1.10, 1.02, 0.98, 0.95, 1.00)
TRAVEL_CALENDAR = (0.70, 0.95, 1.20, 1.05, 1.05, 0.95, 0.85, 0.95, 1.20, 1.25, 1.10, 0.75)

# Log-normal noise (sigma) of the monthly amount per account.
OPEX_NOISE: dict[str, float] = {
    "6100": 0.008,
    "6150": 0.010,
    "6200": 0.080,
    "6300": 0.000,
    "6350": 0.050,
    "6400": 0.040,
    "6500": 0.010,
    "6600": 0.300,
    "6700": 0.150,
    "6800": 0.020,
    "6900": 0.000,
}

# Planning bias applied to every operating-expense budget line (planners assume savings).
OPEX_BUDGET_BIAS = 0.99
BUDGET_ROUNDING = 100.0  # budgets are approved in round figures

# How each account is distributed across cost centres. "default" applies unless a
# business unit has its own split.
COST_CENTER_SPLIT: dict[str, dict[str, dict[str, float]]] = {
    "6100": {
        "RET": {"SAL": 0.55, "MKT": 0.06, "LOG": 0.16, "ADM": 0.12, "TEC": 0.05, "HRS": 0.06},
        "ECM": {"SAL": 0.18, "MKT": 0.20, "LOG": 0.22, "ADM": 0.10, "TEC": 0.25, "HRS": 0.05},
        "WHS": {"SAL": 0.35, "MKT": 0.05, "LOG": 0.38, "ADM": 0.12, "TEC": 0.05, "HRS": 0.05},
        "COR": {"SAL": 0.50, "MKT": 0.08, "LOG": 0.15, "ADM": 0.15, "TEC": 0.06, "HRS": 0.06},
    },
    "6200": {"default": {"MKT": 1.0}},
    "6300": {
        "RET": {"SAL": 0.80, "LOG": 0.12, "ADM": 0.08},
        "default": {"LOG": 0.60, "ADM": 0.40},
    },
    "6350": {
        "RET": {"SAL": 0.80, "LOG": 0.12, "ADM": 0.08},
        "default": {"LOG": 0.60, "ADM": 0.40},
    },
    "6400": {"default": {"LOG": 1.0}},
    "6500": {"default": {"TEC": 0.75, "ADM": 0.15, "SAL": 0.10}},
    "6600": {"default": {"ADM": 0.70, "HRS": 0.15, "TEC": 0.15}},
    "6700": {"default": {"SAL": 0.70, "ADM": 0.20, "MKT": 0.10}},
    "6800": {"default": {"SAL": 1.0}},
    "6900": {
        "RET": {"SAL": 0.60, "LOG": 0.20, "TEC": 0.10, "ADM": 0.10},
        "default": {"LOG": 0.50, "TEC": 0.30, "ADM": 0.20},
    },
}
# Employee benefits follow the salary split.
COST_CENTER_SPLIT["6150"] = COST_CENTER_SPLIT["6100"]


def cost_center_split(account_code: str, bu_code: str) -> dict[str, float]:
    """Return the cost-centre distribution of an account for a business unit."""
    by_unit = COST_CENTER_SPLIT[account_code]
    return by_unit.get(bu_code, by_unit.get("default", {}))
