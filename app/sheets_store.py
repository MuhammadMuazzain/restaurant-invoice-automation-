from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Iterable

import gspread
from google.oauth2.service_account import Credentials


LINEITEM_HEADERS = [
    "dedupe_key",
    "invoice_number",
    "invoice_date",
    "vendor_name",
    "raw_item_name",
    "normalized_item_name",
    "quantity",
    "unit",
    "unit_price",
    "line_total",
    "source_file",
    "ingested_at_utc",
]


def _load_service_account_info(path_or_json: str) -> dict:
    if os.path.exists(path_or_json):
        with open(path_or_json, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(path_or_json)


class GoogleSheetsStore:
    def __init__(self, *, spreadsheet_id: str, worksheet_name: str, service_account_json: str) -> None:
        info = _load_service_account_info(service_account_json)
        creds = Credentials.from_service_account_info(
            info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        self.gc = gspread.authorize(creds)
        self.spreadsheet = self.gc.open_by_key(spreadsheet_id)
        self.worksheet = self._get_or_create_sheet(worksheet_name)
        self._ensure_header()

    def _get_or_create_sheet(self, name: str):
        try:
            return self.spreadsheet.worksheet(name)
        except gspread.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=name, rows=1000, cols=len(LINEITEM_HEADERS))

    def _ensure_header(self) -> None:
        values = self.worksheet.row_values(1)
        if values[: len(LINEITEM_HEADERS)] != LINEITEM_HEADERS:
            self.worksheet.clear()
            self.worksheet.append_row(LINEITEM_HEADERS, value_input_option="RAW")

    def existing_dedupe_keys(self) -> set[str]:
        # Column A = dedupe_key
        col = self.worksheet.col_values(1)
        return {v for v in col[1:] if v}

    def append_lineitems(self, rows: Iterable[list], *, dedupe_keys_existing: set[str]) -> int:
        rows_to_add = [r for r in rows if r and r[0] not in dedupe_keys_existing]
        if not rows_to_add:
            return 0
        self.worksheet.append_rows(rows_to_add, value_input_option="RAW")
        return len(rows_to_add)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

