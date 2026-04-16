from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    COMPANY_NAME: str = 'TechNova Solutions, Inc.'
    INVOICES_DIR: str = 'data/invoices'
    REPORT_FILEPATH: str = 'data/invoices-report.xlsx'

    # Food invoice pipeline
    GOOGLE_SHEETS_SPREADSHEET_ID: str | None = None
    GOOGLE_SHEETS_WORKSHEET_NAME: str = 'LineItems'
    GOOGLE_SERVICE_ACCOUNT_JSON: str | None = Field(
        default=None,
        description="Either a filepath to service_account.json or the JSON string itself.",
    )
    GOOGLE_DRIVE_FOLDER_ID: str | None = None
    PROCESSED_STATE_FILE: str = 'data/processed_state.json'
    ITEM_ALIASES_FILE: str = 'data/item_aliases.csv'

    model_config = SettingsConfigDict(env_file='.env')

settings = Settings()