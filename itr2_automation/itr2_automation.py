"""Automation helpers for preparing ITR-2 figures from common data sources.

This module expects structured data exported from Form 16, AIS, TIS and
Zerodha's tax P&L statement.  The parser is intentionally conservative so that
it can cope with slightly different column headers, yet it relies on the user
following the provided CSV templates in ``sample_data``.

The main entry point is ``main`` which can be run as a script::

    python -m itr2_automation.itr2_automation \
        --form16 sample_data/form16_sample.csv \
        --ais sample_data/ais_sample.csv \
        --tis sample_data/tis_sample.csv \
        --zerodha sample_data/zerodha_pnl_sample.csv \
        --output output.xlsx

The generated workbook contains a ``Summary`` sheet with consolidated numbers
and additional sheets mirroring the raw inputs so that they can be verified.

The output is designed to speed up manual data entry into the Income Tax
Department's offline or online ITR-2 utilities.  The script does *not* submit
any information to the department; it simply performs the mechanical
aggregations and tax calculations.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple

import pandas as pd


class InputFormatError(RuntimeError):
    """Raised when an input file does not adhere to the expected format."""


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


def _slugify(value: str) -> str:
    """Return a lowercase identifier derived from ``value``.

    Examples
    --------
    >>> _slugify("Gross Salary")
    'gross_salary'
    >>> _slugify("Section 80C (PF)")
    'section_80c_pf'
    """

    cleaned = []
    for char in value.lower():
        if char.isalnum():
            cleaned.append(char)
        else:
            cleaned.append("_")
    slug = "".join(cleaned)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


@dataclass
class Form16Data:
    gross_salary: float = 0.0
    exempt_allowances: float = 0.0
    standard_deduction: float = 0.0
    professional_tax: float = 0.0
    other_income_declared: float = 0.0
    tds: float = 0.0
    deductions: MutableMapping[str, float] = field(default_factory=dict)
    extras: MutableMapping[str, float] = field(default_factory=dict)

    @property
    def salary_income(self) -> float:
        """Compute salary income after standard allowances and deductions."""

        return (
            self.gross_salary
            - self.exempt_allowances
            - self.standard_deduction
            - self.professional_tax
        )


@dataclass
class IncomeBreakdown:
    interest_income: float = 0.0
    dividend_income: float = 0.0
    rental_income: float = 0.0
    other_income: float = 0.0
    details: List[Mapping[str, object]] = field(default_factory=list)

    def total(self) -> float:
        return self.interest_income + self.dividend_income + self.rental_income + self.other_income


@dataclass
class CapitalGainsBreakdown:
    stcg_111a: float = 0.0
    ltcg_112a: float = 0.0
    speculative_income: float = 0.0
    non_speculative_income: float = 0.0
    other_gains: float = 0.0
    details: List[Mapping[str, object]] = field(default_factory=list)

    def total(self) -> float:
        return (
            self.stcg_111a
            + self.ltcg_112a
            + self.speculative_income
            + self.non_speculative_income
            + self.other_gains
        )


@dataclass
class TaxComputation:
    total_income: float
    tax_before_cess: float
    health_education_cess: float
    tax_payable: float
    tax_payable_after_tds: float
    rebate_87a: float


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------


def _load_table(path: Path) -> pd.DataFrame:
    """Load a CSV or Excel file into a dataframe.

    Parameters
    ----------
    path:
        Path to the input file.  ``.csv`` and Excel formats (``.xlsx``,
        ``.xlsm``, ``.xls``) are supported.
    """

    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path)
    elif suffix in {".xlsx", ".xls", ".xlsm"}:
        df = pd.read_excel(path)
    else:
        raise InputFormatError(f"Unsupported file extension for {path!s}")

    if df.empty:
        raise InputFormatError(f"No rows found in {path!s}")

    df = df.dropna(how="all")
    if df.empty:
        raise InputFormatError(f"No usable rows found in {path!s}")

    return df


def _pick_column(df: pd.DataFrame, *alternatives: Iterable[str]) -> str:
    """Return the first matching column name from ``alternatives``.

    The comparison is case-insensitive and relies on ``_slugify``.
    """

    slug_to_original = {_slugify(col): col for col in df.columns}
    for names in alternatives:
        for name in names:
            slug = _slugify(name)
            if slug in slug_to_original:
                return slug_to_original[slug]
    raise InputFormatError(
        "None of the expected columns were found. Tried: "
        + ", ".join("/".join(names) for names in alternatives)
    )


def read_form16(path: Path) -> Form16Data:
    """Parse a structured Form 16 export.

    The function expects at least two columns: a *field* identifier and an
    *amount*.  The provided template uses ``Field`` and ``Amount`` columns.
    """

    df = _load_table(path)
    field_col = _pick_column(df, ["field", "section", "component"])
    amount_col = _pick_column(df, ["amount", "value", "amt"])

    data = Form16Data()
    for _, row in df.iterrows():
        raw_field = str(row[field_col]).strip()
        if not raw_field:
            continue

        amount = row[amount_col]
        if pd.isna(amount):
            continue
        try:
            amount_value = float(amount)
        except (TypeError, ValueError) as exc:
            raise InputFormatError(
                f"Invalid amount {amount!r} for field {raw_field!r} in {path!s}"
            ) from exc

        field_slug = _slugify(raw_field)
        target = FORM16_FIELD_MAP.get(field_slug)
        if target == "gross_salary":
            data.gross_salary += amount_value
        elif target == "exempt_allowances":
            data.exempt_allowances += amount_value
        elif target == "standard_deduction":
            data.standard_deduction += amount_value
        elif target == "professional_tax":
            data.professional_tax += amount_value
        elif target == "other_income_declared":
            data.other_income_declared += amount_value
        elif target == "tds":
            data.tds += amount_value
        elif field_slug.startswith("section_80") or field_slug.startswith("80"):
            section_name = raw_field.upper().replace(" ", "")
            data.deductions[section_name] = data.deductions.get(section_name, 0.0) + amount_value
        else:
            data.extras[raw_field] = data.extras.get(raw_field, 0.0) + amount_value

    return data


FORM16_FIELD_MAP: Mapping[str, str] = {
    "gross_salary": "gross_salary",
    "gross_salary_a": "gross_salary",
    "gross_total_income": "gross_salary",
    "allowances_to_the_extent_exempt_under_section10": "exempt_allowances",
    "exempt_allowances": "exempt_allowances",
    "standard_deduction": "standard_deduction",
    "standard_deduction_us_16ia": "standard_deduction",
    "profession_tax": "professional_tax",
    "professional_tax": "professional_tax",
    "section_16_iii_professional_tax": "professional_tax",
    "other_income_declared": "other_income_declared",
    "other_income_from_house_property_declared": "other_income_declared",
    "tds": "tds",
    "tax_deducted_at_source": "tds",
    "tax_deducted": "tds",
}


def read_income_sheet(path: Path) -> IncomeBreakdown:
    """Read AIS/TIS income items."""

    df = _load_table(path)
    category_col = _pick_column(df, ["category", "head", "type"])
    amount_col = _pick_column(df, ["amount", "value", "reported_amount"])
    description_col = None
    for possible in ("description", "details", "source"):
        if possible in df.columns:
            description_col = possible
            break

    breakdown = IncomeBreakdown()
    for _, row in df.iterrows():
        category_raw = str(row[category_col]).strip()
        if not category_raw:
            continue

        amount = row[amount_col]
        if pd.isna(amount):
            continue
        try:
            amount_value = float(amount)
        except (TypeError, ValueError) as exc:
            raise InputFormatError(
                f"Invalid amount {amount!r} for category {category_raw!r} in {path!s}"
            ) from exc

        category_slug = _slugify(category_raw)
        category = INCOME_CATEGORY_MAP.get(category_slug, "other_income")
        if category == "interest_income":
            breakdown.interest_income += amount_value
        elif category == "dividend_income":
            breakdown.dividend_income += amount_value
        elif category == "rental_income":
            breakdown.rental_income += amount_value
        else:
            breakdown.other_income += amount_value

        detail_entry = {
            "Category": category_raw,
            "MappedCategory": category,
            "Amount": amount_value,
        }
        if description_col:
            detail_entry["Description"] = row[description_col]
        breakdown.details.append(detail_entry)

    return breakdown


INCOME_CATEGORY_MAP: Mapping[str, str] = {
    "interest": "interest_income",
    "interest_income": "interest_income",
    "bank_interest": "interest_income",
    "savings_interest": "interest_income",
    "dividend": "dividend_income",
    "dividend_income": "dividend_income",
    "rent": "rental_income",
    "rental_income": "rental_income",
    "house_property": "rental_income",
    "other_income": "other_income",
    "others": "other_income",
    "speculative_income": "other_income",
}


def read_tis(path: Path) -> Tuple[IncomeBreakdown, Dict[str, float], float]:
    """Parse the TIS sheet.

    Returns
    -------
    income_breakdown: :class:`IncomeBreakdown`
        Income components recorded in the TIS.
    deductions: dict
        Chapter VI deduction suggestions captured in the TIS.
    tax_paid: float
        Any advance/self-assessment tax flagged in the TIS.
    """

    df = _load_table(path)
    type_col = _pick_column(df, ["type", "entry_type"])
    amount_col = _pick_column(df, ["amount", "value"])
    category_col = None
    for possible in ("category", "section", "description"):
        if possible in df.columns:
            category_col = possible
            break

    income_breakdown = IncomeBreakdown()
    deductions: Dict[str, float] = {}
    tax_paid = 0.0

    for _, row in df.iterrows():
        entry_type_raw = str(row[type_col]).strip()
        if not entry_type_raw:
            continue

        amount = row[amount_col]
        if pd.isna(amount):
            continue
        try:
            amount_value = float(amount)
        except (TypeError, ValueError) as exc:
            raise InputFormatError(
                f"Invalid amount {amount!r} for entry {entry_type_raw!r} in {path!s}"
            ) from exc

        entry_type = _slugify(entry_type_raw)
        category_value = str(row[category_col]).strip() if category_col else ""

        if entry_type in {"income", "reported_income"}:
            category_slug = _slugify(category_value)
            mapped = INCOME_CATEGORY_MAP.get(category_slug, "other_income")
            if mapped == "interest_income":
                income_breakdown.interest_income += amount_value
            elif mapped == "dividend_income":
                income_breakdown.dividend_income += amount_value
            elif mapped == "rental_income":
                income_breakdown.rental_income += amount_value
            else:
                income_breakdown.other_income += amount_value
            income_breakdown.details.append(
                {
                    "Type": entry_type_raw,
                    "Category": category_value,
                    "MappedCategory": mapped,
                    "Amount": amount_value,
                }
            )
        elif entry_type in {"deduction", "reported_deduction"}:
            section_name = category_value or "Deduction"
            section_name = section_name.upper().replace(" ", "")
            deductions[section_name] = deductions.get(section_name, 0.0) + amount_value
        elif entry_type in {"taxpaid", "tax_paid", "advance_tax", "self_assessment_tax"}:
            tax_paid += amount_value
        else:
            income_breakdown.details.append(
                {
                    "Type": entry_type_raw,
                    "Category": category_value,
                    "MappedCategory": "ignored",
                    "Amount": amount_value,
                }
            )

    return income_breakdown, deductions, tax_paid


def read_zerodha(path: Path) -> CapitalGainsBreakdown:
    """Parse Zerodha tax P&L exports.

    The template expects the following columns: ``Type`` (e.g. ``STCG-Equity``),
    ``Segment`` (e.g. ``Equity Delivery``), ``Amount`` (realised gain/loss) and
    ``Description`` (optional).
    """

    df = _load_table(path)
    type_col = _pick_column(df, ["type", "category"])
    amount_col = _pick_column(df, ["amount", "net", "pnl"])
    description_col = None
    for possible in ("description", "segment", "notes"):
        if possible in df.columns:
            description_col = possible
            break

    breakdown = CapitalGainsBreakdown()
    for _, row in df.iterrows():
        type_raw = str(row[type_col]).strip()
        if not type_raw:
            continue

        amount = row[amount_col]
        if pd.isna(amount):
            continue
        try:
            amount_value = float(amount)
        except (TypeError, ValueError) as exc:
            raise InputFormatError(
                f"Invalid amount {amount!r} for trade type {type_raw!r} in {path!s}"
            ) from exc

        trade_slug = _slugify(type_raw)
        category = ZERODHA_CATEGORY_MAP.get(trade_slug, "other_gains")
        if category == "stcg_111a":
            breakdown.stcg_111a += amount_value
        elif category == "ltcg_112a":
            breakdown.ltcg_112a += amount_value
        elif category == "speculative_income":
            breakdown.speculative_income += amount_value
        elif category == "non_speculative_income":
            breakdown.non_speculative_income += amount_value
        else:
            breakdown.other_gains += amount_value

        detail_entry = {
            "Type": type_raw,
            "MappedCategory": category,
            "Amount": amount_value,
        }
        if description_col:
            detail_entry[description_col.capitalize()] = row[description_col]
        breakdown.details.append(detail_entry)

    return breakdown


ZERODHA_CATEGORY_MAP: Mapping[str, str] = {
    "stcg_equity": "stcg_111a",
    "stcg_equity_delivery": "stcg_111a",
    "ltcg_equity": "ltcg_112a",
    "ltcg_equity_delivery": "ltcg_112a",
    "intraday_equity": "speculative_income",
    "speculative": "speculative_income",
    "futures_options": "non_speculative_income",
    "fno": "non_speculative_income",
    "currency_fno": "non_speculative_income",
    "commodity_fno": "non_speculative_income",
}


# ---------------------------------------------------------------------------
# Tax calculations
# ---------------------------------------------------------------------------


def _slab_tax_old_regime(taxable_income: float) -> float:
    """Compute slab tax (before cess) for the FY 2023-24 old regime."""

    slabs = [
        (250000, 0.0),
        (250000, 0.05),
        (500000, 0.20),
        (math.inf, 0.30),
    ]
    remaining = taxable_income
    lower_limit = 0.0
    tax = 0.0
    for width, rate in slabs:
        if remaining <= 0:
            break
        span = min(remaining, width)
        tax += span * rate
        remaining -= span
        lower_limit += width
    return tax


def compute_tax(
    form16: Form16Data,
    other_income: IncomeBreakdown,
    zerodha: CapitalGainsBreakdown,
    tis_deductions: Mapping[str, float],
    tis_tax_paid: float,
) -> TaxComputation:
    """Calculate tax liability under the old regime with common adjustments."""

    chapter_vi_total = sum(form16.deductions.values()) + sum(tis_deductions.values())

    # Chapter VI deductions reduce the gross total income before tax slabs.
    gross_total_income = (
        form16.salary_income
        + form16.other_income_declared
        + other_income.total()
        + zerodha.speculative_income
        + zerodha.non_speculative_income
        + zerodha.stcg_111a
        + zerodha.ltcg_112a
        + zerodha.other_gains
    )

    total_income_post_deductions = max(0.0, gross_total_income - chapter_vi_total)

    # Separate out components taxed at special rates.
    stcg = max(0.0, zerodha.stcg_111a)
    ltcg = max(0.0, zerodha.ltcg_112a)

    income_for_slabs = max(0.0, total_income_post_deductions - stcg - ltcg)

    slab_tax = _slab_tax_old_regime(income_for_slabs)

    rebate_87a = 0.0
    if total_income_post_deductions <= 500000:
        rebate_87a = min(12500.0, slab_tax)
        slab_tax -= rebate_87a

    stcg_tax = 0.15 * max(0.0, stcg)
    ltcg_taxable = max(0.0, ltcg - 100000.0)
    ltcg_tax = 0.10 * ltcg_taxable

    tax_before_cess = slab_tax + stcg_tax + ltcg_tax
    cess = 0.04 * tax_before_cess
    tax_payable = tax_before_cess + cess

    tds_total = form16.tds + tis_tax_paid
    tax_payable_after_tds = tax_payable - tds_total

    return TaxComputation(
        total_income=total_income_post_deductions,
        tax_before_cess=tax_before_cess,
        health_education_cess=cess,
        tax_payable=tax_payable,
        tax_payable_after_tds=tax_payable_after_tds,
        rebate_87a=rebate_87a,
    )


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------


def _dict_to_dataframe(data: Mapping[str, float], columns: Tuple[str, str]) -> pd.DataFrame:
    rows = [
        {columns[0]: key, columns[1]: value}
        for key, value in sorted(data.items())
    ]
    return pd.DataFrame(rows)


def export_summary(
    output_path: Path,
    form16: Form16Data,
    ais_income: IncomeBreakdown,
    tis_income: IncomeBreakdown,
    tis_deductions: Mapping[str, float],
    tis_tax_paid: float,
    zerodha: CapitalGainsBreakdown,
    tax: TaxComputation,
    metadata: Optional[Mapping[str, object]] = None,
) -> None:
    """Persist the consolidated summary to an Excel workbook."""

    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary_rows = [
        {"Metric": "Salary Income", "Amount": form16.salary_income},
        {"Metric": "Other Income Declared to Employer", "Amount": form16.other_income_declared},
        {"Metric": "AIS Income", "Amount": ais_income.total()},
        {"Metric": "TIS Income", "Amount": tis_income.total()},
        {"Metric": "Speculative Income", "Amount": zerodha.speculative_income},
        {"Metric": "Non-Speculative Business Income", "Amount": zerodha.non_speculative_income},
        {"Metric": "STCG (111A)", "Amount": zerodha.stcg_111a},
        {"Metric": "LTCG (112A)", "Amount": zerodha.ltcg_112a},
        {"Metric": "Other Capital Gains", "Amount": zerodha.other_gains},
        {"Metric": "Chapter VI deductions (Form 16)", "Amount": sum(form16.deductions.values())},
        {"Metric": "Chapter VI deductions (TIS)", "Amount": sum(tis_deductions.values())},
        {"Metric": "Total Income (post deductions)", "Amount": tax.total_income},
        {"Metric": "Tax before cess", "Amount": tax.tax_before_cess},
        {"Metric": "Health & Education Cess", "Amount": tax.health_education_cess},
        {"Metric": "Total Tax Payable", "Amount": tax.tax_payable},
        {"Metric": "TDS + Advance Tax", "Amount": form16.tds + tis_tax_paid},
        {"Metric": "Rebate u/s 87A", "Amount": tax.rebate_87a},
        {"Metric": "Net Tax Payable/Refund", "Amount": tax.tax_payable_after_tds},
    ]

    if metadata:
        for key, value in metadata.items():
            summary_rows.insert(0, {"Metric": str(key), "Amount": value})

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

        salary_map = {
            "Gross Salary": form16.gross_salary,
            "Exempt Allowances": form16.exempt_allowances,
            "Standard Deduction": form16.standard_deduction,
            "Professional Tax": form16.professional_tax,
            "Other Income Declared": form16.other_income_declared,
            "TDS": form16.tds,
        }
        _dict_to_dataframe(salary_map, ("Component", "Amount")).to_excel(
            writer, sheet_name="Salary", index=False
        )

        if form16.deductions:
            _dict_to_dataframe(form16.deductions, ("Section", "Amount")).to_excel(
                writer, sheet_name="Form16 Deductions", index=False
            )
        if form16.extras:
            _dict_to_dataframe(form16.extras, ("Field", "Amount")).to_excel(
                writer, sheet_name="Form16 Extras", index=False
            )

        if ais_income.details:
            pd.DataFrame(ais_income.details).to_excel(
                writer, sheet_name="AIS", index=False
            )
        if tis_income.details:
            pd.DataFrame(tis_income.details).to_excel(
                writer, sheet_name="TIS Income", index=False
            )
        if tis_deductions:
            _dict_to_dataframe(tis_deductions, ("Section", "Amount")).to_excel(
                writer, sheet_name="TIS Deductions", index=False
            )
        if zerodha.details:
            pd.DataFrame(zerodha.details).to_excel(
                writer, sheet_name="Zerodha", index=False
            )


# ---------------------------------------------------------------------------
# Command line interface
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare ITR-2 summary figures")
    parser.add_argument("--form16", type=Path, required=True, help="Path to Form 16 data (CSV/Excel)")
    parser.add_argument("--ais", type=Path, required=True, help="Path to AIS data (CSV/Excel)")
    parser.add_argument("--tis", type=Path, required=True, help="Path to TIS data (CSV/Excel)")
    parser.add_argument("--zerodha", type=Path, required=True, help="Path to Zerodha tax P&L data (CSV/Excel)")
    parser.add_argument("--output", type=Path, required=True, help="Output Excel workbook path")
    parser.add_argument("--fy", type=str, default="2023-24", help="Financial year (for reference)")
    parser.add_argument(
        "--metadata",
        type=str,
        help="JSON string with additional metadata (e.g. {\"PAN\": \"ABCDE1234F\"})",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    form16 = read_form16(args.form16)
    ais_income = read_income_sheet(args.ais)
    tis_income, tis_deductions, tis_tax_paid = read_tis(args.tis)
    zerodha = read_zerodha(args.zerodha)

    metadata = {"Financial Year": args.fy}
    if args.metadata:
        metadata.update(json.loads(args.metadata))

    tax = compute_tax(
        form16=form16,
        other_income=IncomeBreakdown(
            interest_income=ais_income.interest_income + tis_income.interest_income,
            dividend_income=ais_income.dividend_income + tis_income.dividend_income,
            rental_income=ais_income.rental_income + tis_income.rental_income,
            other_income=ais_income.other_income + tis_income.other_income,
        ),
        zerodha=zerodha,
        tis_deductions=tis_deductions,
        tis_tax_paid=tis_tax_paid,
    )

    export_summary(
        output_path=args.output,
        form16=form16,
        ais_income=ais_income,
        tis_income=tis_income,
        tis_deductions=tis_deductions,
        tis_tax_paid=tis_tax_paid,
        zerodha=zerodha,
        tax=tax,
        metadata=metadata,
    )

    print(f"Summary written to {args.output}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    sys.exit(main())
