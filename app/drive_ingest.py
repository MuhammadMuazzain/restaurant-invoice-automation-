from __future__ import annotations

import io
import os
from typing import Iterable

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload


def _creds_from_service_account_info(info: dict) -> Credentials:
    return Credentials.from_service_account_info(
        info,
        scopes=[
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )


def list_pdfs_in_folder(*, service_account_info: dict, folder_id: str) -> list[dict]:
    creds = _creds_from_service_account_info(service_account_info)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    q = f"'{folder_id}' in parents and trashed=false and mimeType='application/pdf'"
    results: list[dict] = []
    page_token = None
    while True:
        resp = (
            drive.files()
            .list(
                q=q,
                fields="nextPageToken, files(id,name,modifiedTime)",
                pageToken=page_token,
            )
            .execute()
        )
        results.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return results


def download_drive_file(
    *,
    service_account_info: dict,
    file_id: str,
    dest_path: str,
) -> None:
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    creds = _creds_from_service_account_info(service_account_info)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    request = drive.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    with open(dest_path, "wb") as f:
        f.write(fh.getvalue())


def safe_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    out = "".join("_" if c in bad else c for c in name)
    return out.strip() or "invoice.pdf"


def ingest_new_pdfs(
    *,
    service_account_info: dict,
    folder_id: str,
    dest_dir: str,
    already_processed_drive_ids: set[str],
) -> Iterable[tuple[str, str]]:
    """
    Yields (drive_file_id, local_path) for newly downloaded PDFs.
    """
    files = list_pdfs_in_folder(service_account_info=service_account_info, folder_id=folder_id)
    for f in files:
        file_id = f["id"]
        if file_id in already_processed_drive_ids:
            continue
        local_path = os.path.join(dest_dir, safe_filename(f.get("name", file_id) or file_id))
        download_drive_file(
            service_account_info=service_account_info,
            file_id=file_id,
            dest_path=local_path,
        )
        yield file_id, local_path

