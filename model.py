from typing import Optional, List
from dataclasses import dataclass

@dataclass(frozen=True)
class ArticleModel:
    title: str
    company: str
    location: str
    detail_page_url: str
    salary: str
    job_types: str
    description: str