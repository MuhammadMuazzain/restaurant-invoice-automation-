# Invoice Processor (Food Distributor Invoices → Google Sheets + Insights)

An automated workflow to process weekly distributor food invoices and turn them into structured data + ongoing reporting:

- **Ingestion**: process PDFs from `data/invoices/` and optionally auto-download new PDFs from a **Google Drive folder**
- **Extraction (Claude preferred)**: extract **item names, quantities/units, unit price, line totals**, plus invoice metadata
- **Normalization**: map distributor naming variations to consistent item names (`data/item_aliases.csv`)
- **Storage (“database”)**: append line-items into **Google Sheets** with **dedupe**
- **Insights**: generate local CSV reports for:
  - monthly average price per item
  - weekly usage (quantity) per item
  - price-change anomaly flags

This repo also keeps the original “financial invoice → Excel report” pipeline (OpenAI-based) as `process-invoices`.

## Similar GitHub project (reference)

- `https://github.com/ShafqaatMalik/llm-based-invoice-ocr`

## Project structure (key files)

- `app/food_pipeline.py`: end-to-end Drive/Folder → LLM → normalize → Sheets → reports
- `app/llm_extract.py`: Claude/OpenAI extraction wrapper (vision + JSON)
- `app/normalize.py`: item-name normalization (aliases + fuzzy matching)
- `app/sheets_store.py`: Google Sheets append + dedupe header management
- `data/item_aliases.csv`: your normalization dictionary (edit this over time)

## Setup

### Prerequisites

- Python 3.11+
- For PDF-to-image: Poppler installed and available on PATH (required by `pdf2image`)

### Install (pip)

```bash
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

### Configure environment

Copy `.env.example` → `.env` and set at minimum:

- **Claude (preferred)**: `ANTHROPIC_API_KEY`
- **Google Sheets**:
  - `GOOGLE_SHEETS_SPREADSHEET_ID`
  - `GOOGLE_SERVICE_ACCOUNT_JSON` (either a path to `service_account.json` OR the JSON content as a string)

Optional:

- **Google Drive auto-ingest**: `GOOGLE_DRIVE_FOLDER_ID`
- **OpenAI fallback**: `OPENAI_API_KEY`

## Usage

### Food invoices → Google Sheets + reports

1. Put PDFs into `data/invoices/` (or set `GOOGLE_DRIVE_FOLDER_ID` to ingest from Drive).
2. Run:

```bash
python -m app.main_food
```

Outputs:

- Google Sheet tab `LineItems` (or `GOOGLE_SHEETS_WORKSHEET_NAME`)
- Local reports in `data/reports/`:
  - `monthly_avg_price_per_item.csv`
  - `weekly_usage_per_item.csv`
  - `price_change_anomalies.csv`

### Original pipeline (financial invoices → Excel)

```bash
python -m app.main_financial
```

## Notes on long-term accuracy

- Add new distributor naming variants into `data/item_aliases.csv` over time.
- Dedupe is handled via a stable line-item key (invoice + date + vendor + line index + raw item name).

made with 🔥 by Muhammad Muazzain
