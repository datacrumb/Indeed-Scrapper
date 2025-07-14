from model import ArticleModel
from typing import List
import gspread

class GoogleSheets:
    HEADERS = [
        "Title",
        "Company",
        "Location",
        "Detail Page URL",
        "Salary",
        "Job Types",
        "Description",
    ]

    def __init__(self):
        self.client = gspread.service_account(filename="credentials.json")
        self.sheet = self.client.open('Indeed Jobs').sheet1
        self.ensure_headers()

    def ensure_headers(self):
        headers = self.sheet.row_values(1)
        if headers != self.HEADERS:
            self.sheet.update("A1", [self.HEADERS])

    def get_existing_rows(self):
        rows = self.sheet.get_all_values()
        return rows[1:]  # Skip header

    def get_existing_detail_urls(self) -> set:
        existing_rows = self.get_existing_rows()
        # Detail Page URL is column 4 (index 3)
        return set(row[3].strip() for row in existing_rows if len(row) > 3 and row[3].strip())

    def save_to_google_sheets(self, articles: List[ArticleModel]):
        try:
            existing_urls = self.get_existing_detail_urls()
            rows_to_add = []

            for article in articles:
                url = str(article.detail_page_url or "N/A")
                if url in existing_urls:
                    continue

                row = [
                    article.title,
                    article.company,
                    article.location,
                    article.detail_page_url,
                    article.salary,
                    article.job_types,
                    article.description,
                ]

                rows_to_add.append(row)
                existing_urls.add(url)

            if rows_to_add:
                self.sheet.append_rows(rows_to_add, value_input_option="USER_ENTERED")
                print(f"✅ Added {len(rows_to_add)} new articles to Google Sheets.")
            else:
                print("⚠️ No new articles to add (all duplicates).")

        except Exception as e:
            print("❌ Google Sheets setup or fetch failed.")
            print(f"Details: {type(e).__name__}: {e}")
