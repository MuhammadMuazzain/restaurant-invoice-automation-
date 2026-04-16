import asyncio
from app.extraction import extract_invoices_data
from app.processing import (
    build_invoices_dataframe, generate_financial_summary, create_excel_report
)
from app.config import settings
from app.food_pipeline import run_food_pipeline

async def process_invoices():
    invoices_filenames, invoices_json = await extract_invoices_data(settings.INVOICES_DIR)
    invoices_df = build_invoices_dataframe(invoices_filenames, invoices_json)
    total_s, monthly_df = generate_financial_summary(invoices_df)
    create_excel_report(invoices_df, total_s, monthly_df, settings.REPORT_FILEPATH)

def main():
    asyncio.run(process_invoices())


def main_food():
    run_food_pipeline()


if __name__ == '__main__':
    main()