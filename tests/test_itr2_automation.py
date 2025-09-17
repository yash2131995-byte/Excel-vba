from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from itr2_automation.itr2_automation import (
    IncomeBreakdown,
    compute_tax,
    export_summary,
    read_form16,
    read_income_sheet,
    read_tis,
    read_zerodha,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "itr2_automation" / "sample_data"


def test_pipeline(tmp_path):
    form16 = read_form16(DATA_DIR / "form16_sample.csv")
    ais_income = read_income_sheet(DATA_DIR / "ais_sample.csv")
    tis_income, tis_deductions, tis_tax_paid = read_tis(DATA_DIR / "tis_sample.csv")
    zerodha = read_zerodha(DATA_DIR / "zerodha_pnl_sample.csv")

    combined_income = IncomeBreakdown(
        interest_income=ais_income.interest_income + tis_income.interest_income,
        dividend_income=ais_income.dividend_income + tis_income.dividend_income,
        rental_income=ais_income.rental_income + tis_income.rental_income,
        other_income=ais_income.other_income + tis_income.other_income,
    )

    tax = compute_tax(
        form16=form16,
        other_income=combined_income,
        zerodha=zerodha,
        tis_deductions=tis_deductions,
        tis_tax_paid=tis_tax_paid,
    )

    assert tax.tax_payable > 0
    assert tax.total_income > 0
    assert tax.tax_payable_after_tds != 0

    output_path = tmp_path / "summary.xlsx"
    export_summary(
        output_path=output_path,
        form16=form16,
        ais_income=ais_income,
        tis_income=tis_income,
        tis_deductions=tis_deductions,
        tis_tax_paid=tis_tax_paid,
        zerodha=zerodha,
        tax=tax,
        metadata={"Financial Year": "2023-24"},
    )

    assert output_path.exists()

    summary_df = pd.read_excel(output_path, sheet_name="Summary")
    assert "Net Tax Payable/Refund" in summary_df["Metric"].values
    numeric_amounts = pd.to_numeric(summary_df["Amount"], errors="coerce").fillna(0)
    assert (numeric_amounts.abs() > 0).any()

