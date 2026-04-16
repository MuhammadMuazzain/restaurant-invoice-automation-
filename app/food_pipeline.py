from __future__ import annotations

import json
import os
from collections.abc import Iterable

import pandas as pd
from pydantic import ValidationError

from app.config import settings
from app.drive_ingest import ingest_new_pdfs
from app.food_models import FoodInvoice
from app.food_prompt import FOOD_INVOICE_SYSTEM_PROMPT
from app.llm_extract import LlmExtractor
from app.normalize import ItemNormalizer
from app.pdf_utils import pdf_to_base64_png_images
from app.sheets_store import GoogleSheetsStore, utc_now_iso
from app.state import ProcessedState


def _load_service_account_info(path_or_json: str) -> dict:
    if os.path.exists(path_or_json):
        with open(path_or_json, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(path_or_json)


def _dedupe_key(invoice_number: str | None, invoice_date: str | None, vendor: str | None, line_idx: int, raw: str) -> str:
    inv = (invoice_number or "").strip().lower()
    dt = (invoice_date or "").strip()
    v = (vendor or "").strip().lower()
    r = (raw or "").strip().lower()
    return f"{inv}|{dt}|{v}|{line_idx}|{r}"


def invoice_to_rows(*, source_file: str, inv: FoodInvoice, normalizer: ItemNormalizer) -> list[list]:
    ingested_at = utc_now_iso()
    invoice_date = inv.invoice_date.isoformat() if inv.invoice_date else None
    rows: list[list] = []
    for idx, li in enumerate(inv.line_items, 1):
        norm = normalizer.normalize(li.raw_item_name)
        key = _dedupe_key(inv.invoice_number, invoice_date, inv.vendor_name, idx, li.raw_item_name)
        rows.append(
            [
                key,
                inv.invoice_number,
                invoice_date,
                inv.vendor_name,
                li.raw_item_name,
                norm.normalized_name,
                li.quantity,
                li.unit,
                li.unit_price,
                li.line_total,
                os.path.basename(source_file),
                ingested_at,
            ]
        )
    return rows


def run_food_pipeline() -> None:
    state = ProcessedState.load(settings.PROCESSED_STATE_FILE)

    # Optional: ingest new PDFs from Drive
    if settings.GOOGLE_DRIVE_FOLDER_ID and settings.GOOGLE_SERVICE_ACCOUNT_JSON:
        info = _load_service_account_info(settings.GOOGLE_SERVICE_ACCOUNT_JSON)
        already = {x.removeprefix("drive:") for x in state.processed_files if x.startswith("drive:")}
        for drive_id, local_path in ingest_new_pdfs(
            service_account_info=info,
            folder_id=settings.GOOGLE_DRIVE_FOLDER_ID,
            dest_dir=settings.INVOICES_DIR,
            already_processed_drive_ids=already,
        ):
            state.processed_files.add(f"drive:{drive_id}")
            state.processed_files.discard(local_path)  # keep deterministic; local file processed later

    extractor = LlmExtractor(
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        openai_api_key=settings.OPENAI_API_KEY,
        preferred="claude",
    )
    normalizer = ItemNormalizer(settings.ITEM_ALIASES_FILE)

    sheets: GoogleSheetsStore | None = None
    if settings.GOOGLE_SHEETS_SPREADSHEET_ID and settings.GOOGLE_SERVICE_ACCOUNT_JSON:
        sheets = GoogleSheetsStore(
            spreadsheet_id=settings.GOOGLE_SHEETS_SPREADSHEET_ID,
            worksheet_name=settings.GOOGLE_SHEETS_WORKSHEET_NAME,
            service_account_json=settings.GOOGLE_SERVICE_ACCOUNT_JSON,
        )
        existing_keys = sheets.existing_dedupe_keys()
    else:
        existing_keys = set()

    os.makedirs(settings.INVOICES_DIR, exist_ok=True)

    new_rows: list[list] = []
    processed_count = 0
    for filename in sorted(os.listdir(settings.INVOICES_DIR)):
        if not filename.lower().endswith(".pdf"):
            continue
        full_path = os.path.join(settings.INVOICES_DIR, filename)
        if full_path in state.processed_files:
            continue

        base64_imgs = pdf_to_base64_png_images(full_path, max_pages=3)
        raw = extractor.extract_food_invoice_json(
            base64_png_images=base64_imgs,
            system_prompt=FOOD_INVOICE_SYSTEM_PROMPT,
        )

        try:
            inv = FoodInvoice(**raw)
        except ValidationError:
            # If schema mismatch, keep minimal structure to avoid losing items
            inv = FoodInvoice.model_validate(raw)

        new_rows.extend(invoice_to_rows(source_file=full_path, inv=inv, normalizer=normalizer))
        state.processed_files.add(full_path)
        processed_count += 1

    appended = 0
    if sheets:
        appended = sheets.append_lineitems(new_rows, dedupe_keys_existing=existing_keys)

    state.save(settings.PROCESSED_STATE_FILE)

    # Local reports from newly added rows + existing sheet (if configured)
    if sheets and appended > 0:
        _write_local_reports_from_sheet(sheets)

    print(f"Processed PDFs: {processed_count}")
    print(f"Prepared rows: {len(new_rows)}")
    print(f"Appended rows (deduped): {appended}")


def _write_local_reports_from_sheet(sheets: GoogleSheetsStore) -> None:
    values = sheets.worksheet.get_all_records()
    if not values:
        return
    df = pd.DataFrame(values)
    for col in ["quantity", "unit_price", "line_total"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "invoice_date" in df.columns:
        df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")

    reports_dir = os.path.join("data", "reports")
    os.makedirs(reports_dir, exist_ok=True)

    # Monthly average unit price per item
    if "invoice_date" in df.columns and "normalized_item_name" in df.columns and "unit_price" in df.columns:
        monthly = df.dropna(subset=["invoice_date"]).copy()
        monthly["year_month"] = monthly["invoice_date"].dt.to_period("M").astype(str)
        monthly_avg = (
            monthly.groupby(["year_month", "normalized_item_name"], as_index=False)["unit_price"]
            .mean()
            .rename(columns={"unit_price": "avg_unit_price"})
        )
        monthly_avg.to_csv(os.path.join(reports_dir, "monthly_avg_price_per_item.csv"), index=False)

    # Weekly usage (sum quantities) per item
    if "invoice_date" in df.columns and "normalized_item_name" in df.columns and "quantity" in df.columns:
        weekly = df.dropna(subset=["invoice_date"]).copy()
        weekly["year_week"] = weekly["invoice_date"].dt.strftime("%G-W%V")
        weekly_usage = (
            weekly.groupby(["year_week", "normalized_item_name"], as_index=False)["quantity"]
            .sum()
            .rename(columns={"quantity": "total_quantity"})
        )
        weekly_usage.to_csv(os.path.join(reports_dir, "weekly_usage_per_item.csv"), index=False)

    # Price change anomalies: compare latest month vs previous month
    if "invoice_date" in df.columns and "normalized_item_name" in df.columns and "unit_price" in df.columns:
        tmp = df.dropna(subset=["invoice_date", "unit_price"]).copy()
        tmp["year_month"] = tmp["invoice_date"].dt.to_period("M")
        m = (
            tmp.groupby(["year_month", "normalized_item_name"], as_index=False)["unit_price"]
            .mean()
            .sort_values(["normalized_item_name", "year_month"])
        )
        m["prev_avg_unit_price"] = m.groupby("normalized_item_name")["unit_price"].shift(1)
        m["pct_change"] = (m["unit_price"] - m["prev_avg_unit_price"]) / m["prev_avg_unit_price"]
        flagged = m[m["pct_change"].abs() >= 0.15].copy()
        flagged["year_month"] = flagged["year_month"].astype(str)
        flagged.to_csv(os.path.join(reports_dir, "price_change_anomalies.csv"), index=False)

