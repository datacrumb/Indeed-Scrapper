import openai
import os
from typing import List
import re

openai_api_key = os.getenv("OPENAI_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY is not set")

def extract_python_list(text: str) -> str:
    # Remove markdown code block if present
    code_block = re.search(r"```(?:python)?\s*([\s\S]*?)\s*```", text)
    if code_block:
        return code_block.group(1).strip()
    return text.strip()

async def generate_tags(job_description: str) -> List[str]:
    client = openai.AsyncOpenAI(api_key=openai_api_key)
    prompt = f"""
    Generate a list of relevant tags from the following job description: {job_description}\n
    Tags should be relevant to the job description and should be in the form of a list of comma-separated strings.

    Tags should be short and concise, and should not contain any unnecessary words or phrases.

    Examples: [Full-Time, Remote, Fresher, On-site, Internship, Part-Time, Entry-Level]

    Always return a python list of tags, if there are no relevant tags in the description, return an empty python list.

    Never include any other text beside python list of tags, only return a python list.
    ONLY return a python list.
    ONLY return four tags, from example or relevant tags.
    """
    response = await client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100,
        temperature=0.2,
    )
    text = response.choices[0].message.content.strip()
    # Remove code block if present
    text = extract_python_list(text)
    try:
        tags = eval(text)
        if isinstance(tags, list):
            return tags
        else:
            return []
    except Exception:
        return []

async def clean_job_title(title: str, description: str) -> str:
    client = openai.AsyncOpenAI(api_key=openai_api_key)
    prompt = f"""
    Given the following job title and job description, return a short, clear, and relevant job title. Remove any unnecessary or irrelevant text, and make the title concise and professional. Only return the cleaned job title as a string, with no extra text or formatting.

    Job Title: {title}
    Job Description: {description}
    """
    response = await client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=30,
        temperature=0.2,
    )
    cleaned = response.choices[0].message.content.strip()
    # Remove code block if present
    cleaned = re.sub(r"^```[a-zA-Z]*\\s*|\\s*```$", "", cleaned).strip()
    return cleaned

if __name__ == "__main__":
    import sys
    import asyncio
    from sheets import GoogleSheets

    async def tag_all_descriptions():
        try:
            import time
            gs = GoogleSheets()
            rows = gs.get_existing_rows()
            total = len(rows)
            print(f"Processing {total} rows...")
            batch_size = 5
            tags_list = []
            cleaned_titles = []
            row_indices = []
            for idx, row in enumerate(rows, start=1):
                if len(row) > 7 and row[7].strip():
                    print(f"Row {idx}/{total}: Tags already exist, skipping. Tags: {[tag.strip() for tag in row[7].split(',')]}")
                    continue  # Instantly skip rows with tags
                description = row[6] if len(row) > 6 else ""
                title = row[0] if len(row) > 0 else ""
                print(f"Row {idx}/{total}: Cleaning job title...")
                cleaned_title = await clean_job_title(title, description)
                print(f"Row {idx}/{total}: Cleaned title: {cleaned_title}")
                print(f"Row {idx}/{total}: Generating tags...")
                tags = await generate_tags(description)
                print(f"Row {idx}/{total}: Tags generated: {tags}")
                cleaned_titles.append(cleaned_title)
                tags_list.append(tags)
                row_indices.append(idx + 1)  # +1 for header offset
                if len(tags_list) == batch_size:
                    gs.update_titles_and_tags_partial(cleaned_titles, tags_list, row_indices)
                    print(f"Batch update: rows {row_indices[0]} to {row_indices[-1]} updated.")
                    tags_list = []
                    cleaned_titles = []
                    row_indices = []
                    time.sleep(2)  # Wait 2 seconds after each batch
            # Final batch
            if tags_list:
                gs.update_titles_and_tags_partial(cleaned_titles, tags_list, row_indices)
                print(f"Batch update: rows {row_indices[0]} to {row_indices[-1]} updated.")
                time.sleep(2)
            print("Done! All tags and titles updated.")
        except Exception as e:
            print(f"Error: {e}")

    asyncio.run(tag_all_descriptions())