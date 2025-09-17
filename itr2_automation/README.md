# ITR-2 Automation Helpers

This folder contains a Python utility that consolidates details from Form 16,
AIS, TIS and Zerodha tax P&L statements to produce a filing-ready summary for
ITR-2 (old regime).  The output workbook mimics the sections in the Income Tax
Department's utilities so that you only need to copy numbers instead of
performing the calculations manually.

## Key features

* Normalises Form 16 salary values and employer deductions.
* Aggregates AIS/TIS income heads such as interest, dividends and rental
  income.
* Summarises Zerodha capital gains (STCG/LTCG) and speculative/non-speculative
  business income.
* Computes Chapter VI deduction totals, tax slab liability (old regime for
  FY2023-24/AY2024-25) including rebate under section 87A, STCG/LTCG special
  rates and 4% cess.
* Produces an Excel workbook with a `Summary` sheet and supporting tabs for
  each data source so that you can cross-check the inputs.

## Installation

1. Install Python 3.9+.
2. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Export data from Form 16, AIS, TIS and Zerodha into the provided CSV
   templates located under `sample_data/`.  The required columns are:

   * **Form 16** – columns `Field`, `Description`, `Amount`.
   * **AIS/TIS** – columns `Category`/`Type`, optional `Description`, and
     `Amount`.
   * **Zerodha P&L** – columns `Type`, optional `Segment`/`Description`, and
     `Amount`.

   You can rename the files but keep the column names intact.

2. Run the script:

   ```bash
   python -m itr2_automation.itr2_automation \
       --form16 path/to/form16.csv \
       --ais path/to/ais.csv \
       --tis path/to/tis.csv \
       --zerodha path/to/zerodha.csv \
       --output itr2_summary.xlsx \
       --metadata '{"PAN": "ABCDE1234F", "Name": "Your Name"}'
   ```

3. Open the generated workbook (`itr2_summary.xlsx`).  Use the numbers in the
   `Summary` sheet when filling out the ITR-2 online/offline forms.  The
   additional tabs retain the granular data so you can reconcile discrepancies
   with the AIS/TIS portal.

## Notes

* The script does **not** submit the return or log into any government
  services.  It only consolidates numbers to speed up filing.
* The defaults target FY2023-24 (AY2024-25).  Update the `--fy` flag if you are
  preparing a different year.  Tax slabs may need adjustments for other years.
* If your Form 16/AIS/TIS headers differ, tweak the CSV to align with the
  templates so that the parser can recognise each field.
* Zerodha exports sometimes include negative numbers for losses.  The script
  carries over the sign so set off can be performed manually in the ITR
  schedules.
