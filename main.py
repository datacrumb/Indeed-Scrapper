from playwright.async_api import async_playwright
import asyncio
import json
import random
from sheets import GoogleSheets
from model import ArticleModel

def fix_cookies(cookies):
    fixed = []
    for cookie in cookies:
        # Fix sameSite values
        if "sameSite" in cookie:
            if cookie["sameSite"] == "no_restriction":
                cookie["sameSite"] = "None"
            elif cookie["sameSite"] == "unspecified":
                cookie.pop("sameSite")
        # Remove fields not accepted by Playwright
        for field in ["hostOnly", "storeId", "id"]:
            cookie.pop(field, None)
        # Playwright expects 'expires' instead of 'expirationDate'
        if "expirationDate" in cookie:
            cookie["expires"] = int(cookie["expirationDate"])
            cookie.pop("expirationDate")
        fixed.append(cookie)
    return fixed

async def handle_cloudflare_checkbox(page):
    try:
        # Look for the Cloudflare challenge div (the one containing cf-turnstile-response)
        challenge_div = await page.query_selector('div[id^="ovEdv1"][style*="display: grid"]')
        
        if challenge_div:
            print("Cloudflare challenge detected. Simulating mouse activity...")
            # Simulate random mouse movement and activity
            box = await challenge_div.bounding_box()
            if box:
                for _ in range(random.randint(3, 7)):
                    x = box['x'] + random.uniform(5, box['width'] - 5)
                    y = box['y'] + random.uniform(5, box['height'] - 5)
                    await page.mouse.move(x, y, steps=random.randint(5, 15))
                    if random.random() < 0.3:
                        await page.mouse.down()
                        await asyncio.sleep(random.uniform(0.05, 0.2))
                        await page.mouse.up()
                    await asyncio.sleep(random.uniform(0.1, 0.4))
                # Optionally scroll a bit
                if random.random() < 0.5:
                    await page.mouse.wheel(0, random.randint(20, 100))
            await asyncio.sleep(2)
            print("Waiting before clicking Cloudflare challenge div...")
            await asyncio.sleep(11)
            # Click the challenge div (this should trigger the Turnstile widget)
            await challenge_div.click()
            print("Clicked Cloudflare challenge div clicked!")
            # Wait for the challenge to process
            await asyncio.sleep(3)
            # Check if the challenge was successful by looking for the loading state to disappear
            try:
                await page.wait_for_selector('div[id^="iZbAO5"][style*="display: none"]', timeout=20000)
                print("Cloudflare challenge appears to be completed")
            except:
                print("Cloudflare challenge may still be processing...")
        else:
            print("No Cloudflare challenge detected")
    except Exception as e:
        print("Cloudflare detection failed:", e)

async def scrape_job_details_from_url(context, job_url):
    page = await context.new_page()
    try:
        await page.goto(job_url)
        await handle_cloudflare_checkbox(page)
        await page.wait_for_selector('div.jobsearch-JobComponent', timeout=60000)
        await asyncio.sleep(2)
        details = await page.evaluate("""
            () => {
                const pane = document.querySelector('div.jobsearch-JobComponent');
                if (!pane) return {};
                // Job Title
                const title = pane.querySelector('h1[data-testid="jobsearch-JobInfoHeader-title"]')?.innerText ||
                              pane.querySelector('h2[data-testid="jobsearch-JobInfoHeader-title"]')?.innerText || '';
                // Company Name
                const company = pane.querySelector('div[data-testid="inlineHeader-companyName"] span')?.innerText || '';
                // Location
                const location = pane.querySelector('div[data-testid="jobsearch-JobInfoHeader-companyLocation"] span')?.innerText || '';
                // Salary
                const salary = pane.querySelector('#salaryInfoAndJobType span')?.innerText || '';
                // Job Types (collect all)
                const jobTypes = Array.from(pane.querySelectorAll('button[data-testid$="-tile"] span')).map(e => e.innerText).join(', ');
                // Full Description
                const description = pane.querySelector('#jobDescriptionText')?.innerText || '';
                return { title, company, location, salary, jobTypes, description };
            }
        """)
        details['job_url'] = job_url
        return details
    except Exception as e:
        print(f"Error scraping job at {job_url}: {e}")
        return None
    finally:
        await page.close()

async def main():
    async with async_playwright() as p:
        # Set a real user-agent and stealth scripts
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        )
        browser = await p.chromium.launch(headless=False, channel="chrome")
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="Asia/Karachi"
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()
        page.set_default_timeout(120000)  # Increased to 2 minutes
        # Load and fix cookies
        with open("indeed_cookies.json", "r") as f:
            cookies = json.load(f)
        cookies = fix_cookies(cookies)
        await page.context.add_cookies(cookies)
        await page.goto("https://pk.indeed.com/jobs?l=Karachi&radius=0&vjk=85b4faff748f01bf")
        await handle_cloudflare_checkbox(page)
        print("If you see a Cloudflare challenge, solve it manually in the browser window.")
        await asyncio.sleep(30)

        all_jobs = []
        scraped_urls = set()
        page_num = 1
        google_sheets = GoogleSheets()

        while True:
            await page.wait_for_selector("h2.jobTitle a.jcs-JobTitle", timeout=20000)
            job_links = await page.query_selector_all("h2.jobTitle a.jcs-JobTitle")
            print(f"Found {len(job_links)} jobs on the page.")

            # Collect all job URLs on the page
            job_urls = []
            for job_link in job_links:
                job_url = await job_link.get_attribute('href')
                if job_url:
                    if job_url.startswith('/'):
                        job_url = "https://pk.indeed.com" + job_url
                    job_urls.append(job_url)

            for i, job_url in enumerate(job_urls):
                if job_url in scraped_urls:
                    print(f"Skipping already scraped job: {job_url}")
                    continue
                print(f"Scraping job {i+1} (Page {page_num}): {job_url}")
                details = await scrape_job_details_from_url(context, job_url)
                if details:
                    all_jobs.append(details)
                    scraped_urls.add(job_url)
                    print(json.dumps(details, indent=2, ensure_ascii=False))
                    # Convert details dict to ArticleModel and append to Google Sheets
                    article = ArticleModel(
                        title=details.get('title', 'NOT FOUND'),
                        company=details.get('company', 'NOT FOUND'),
                        location=details.get('location', 'NOT FOUND'),
                        detail_page_url=details.get('job_url', 'NOT FOUND'),
                        salary=details.get('salary', 'NOT FOUND'),
                        job_types=details.get('jobTypes', 'NOT FOUND'),
                        description=details.get('description', 'NOT FOUND'),
                    )
                    google_sheets.save_to_google_sheets([article])
                await asyncio.sleep(2)  # Delay to mimic human behavior

            # Pagination: look for the next page button
            next_button = await page.query_selector('a[data-testid="pagination-page-next"]')
            if next_button:
                next_href = await next_button.get_attribute('href')
                if next_href:
                    next_url = "https://pk.indeed.com" + next_href
                    print(f"Navigating to next page: {next_url}")
                    await page.goto(next_url)
                    await asyncio.sleep(2)  # Small delay to mimic human behavior
                    await handle_cloudflare_checkbox(page)
                    page_num += 1
                    await asyncio.sleep(2)  # Small delay to mimic human behavior
                else:
                    print("No next page href found. Stopping.")
                    break
            else:
                print("No next page button found. Stopping.")
                break

        # Optionally, save all_jobs to a file
        with open("indeed_jobs.json", "w", encoding="utf-8") as f:
            json.dump(all_jobs, f, ensure_ascii=False, indent=2)

        await context.close()

asyncio.run(main())