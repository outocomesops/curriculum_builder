"""
PDF downloader — scrapes a webpage for PDF links and downloads them locally.
"""
from __future__ import annotations

import re
import urllib.parse
from pathlib import Path
from typing import Callable

import requests
from bs4 import BeautifulSoup


def scrape_pdf_links(page_url: str, timeout: int = 15) -> list[str]:
    """Return absolute PDF URLs found on the given page."""
    resp = requests.get(
        page_url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    seen: set[str] = set()
    links: list[str] = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        absolute = urllib.parse.urljoin(page_url, href)
        parsed = urllib.parse.urlparse(absolute)
        # accept .pdf in path or explicit pdf content-type hint in query
        if parsed.path.lower().endswith(".pdf") and absolute not in seen:
            seen.add(absolute)
            links.append(absolute)

    return links


def download_pdfs(
    pdf_urls: list[str],
    dest_folder: Path,
    timeout: int = 60,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[dict]:
    """
    Download PDF URLs into dest_folder.

    Returns list of dicts: {url, filename, path, error}.
    """
    dest_folder.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    for i, url in enumerate(pdf_urls):
        if progress_callback:
            progress_callback(i, len(pdf_urls), url)

        raw_name = Path(urllib.parse.urlparse(url).path).name or f"document_{i + 1}.pdf"
        # decode percent-encoded chars (e.g. %20 → space) then sanitize
        raw_name = urllib.parse.unquote(raw_name)
        filename = re.sub(r"[^\w\-_. ]", "_", raw_name)
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        dest_path = dest_folder / filename

        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0"},
                stream=True,
            )
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=16_384):
                    f.write(chunk)
            results.append({"url": url, "filename": filename, "path": dest_path, "error": None})
        except Exception as exc:
            results.append({"url": url, "filename": filename, "path": None, "error": str(exc)})

    return results
