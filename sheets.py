from model import ArticleModel
from typing import List
import gspread

class GoogleSheets:
    HEADERS = [
        "Title",
        "Company",
        "Location",
        "Link",
        "Salary",
        "Job Types",
        "Description",
        'Tags'
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

    def add_tags_column(self, tags_list: list):
        # Ensure header has "Tags" in column H
        headers = self.sheet.row_values(1)
        if len(headers) < 8 or headers[7] != "Tags":
            if len(headers) < 8:
                headers += ["Tags"]
            else:
                headers[7] = "Tags"
            self.sheet.update("A1", [headers])

        # Write tags to column H (index 8) for each row
        for i, tags in enumerate(tags_list, start=2):  # start=2 to skip header
            self.sheet.update_cell(i, 8, ", ".join(tags))

    def add_tags_column_partial(self, tags_list: list, row_indices: list, max_retries=3, delay=2):
        import time
        import gspread
        from requests.exceptions import ReadTimeout
        # Ensure header has "Tags" in column H
        headers = self.sheet.row_values(1)
        if len(headers) < 8 or headers[7] != "Tags":
            if len(headers) < 8:
                headers += ["Tags"]
            else:
                headers[7] = "Tags"
            self.sheet.update("A1", [headers])

        # Update only the specified cells in column H
        cell_list = [self.sheet.cell(row_idx, 8) for row_idx in row_indices]
        for i, cell in enumerate(cell_list):
            cell.value = ", ".join(tags_list[i])
        for attempt in range(max_retries):
            try:
                self.sheet.update_cells(cell_list)
                return
            except (gspread.exceptions.APIError, ReadTimeout) as e:
                print(f"Batch update failed (attempt {attempt+1}/{max_retries}): {e}")
                time.sleep(delay)
        print("Batch update failed after retries.")

    def update_titles_and_tags_partial(self, cleaned_titles: list, tags_list: list, row_indices: list, max_retries=3, delay=2):
        import time
        import gspread
        from requests.exceptions import ReadTimeout
        # Ensure header has "Tags" in column H
        headers = self.sheet.row_values(1)
        if len(headers) < 8 or headers[7] != "Tags":
            if len(headers) < 8:
                headers += ["Tags"]
            else:
                headers[7] = "Tags"
            self.sheet.update("A1", [headers])

        # Prepare cells for both title (A) and tags (H)
        title_cells = [self.sheet.cell(row_idx, 1) for row_idx in row_indices]
        tag_cells = [self.sheet.cell(row_idx, 8) for row_idx in row_indices]
        for i, cell in enumerate(title_cells):
            cell.value = cleaned_titles[i]
        for i, cell in enumerate(tag_cells):
            cell.value = ", ".join(tags_list[i])
        all_cells = title_cells + tag_cells
        for attempt in range(max_retries):
            try:
                self.sheet.update_cells(all_cells)
                return
            except (gspread.exceptions.APIError, ReadTimeout) as e:
                print(f"Batch update failed (attempt {attempt+1}/{max_retries}): {e}")
                time.sleep(delay)
        print("Batch update failed after retries.")