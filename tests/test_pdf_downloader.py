from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from loaders import pdf_downloader
from tests.conftest import FakeResponse


HTML = """
<html><body>
  <a href="/files/doc1.pdf">Doc 1</a>
  <a href="https://other.test/docs/Doc%20Two.pdf">Doc 2 with spaces</a>
  <a href="/files/doc1.pdf">Duplicate Doc 1</a>
  <a href="/page.html">Not a PDF</a>
</body></html>
"""


@patch("loaders.pdf_downloader.requests.get")
def test_scrape_pdf_links_finds_absolute_deduped(mock_get):
    mock_get.return_value = FakeResponse(text=HTML, status_code=200)
    links = pdf_downloader.scrape_pdf_links("https://example.test/catalog")
    assert "https://example.test/files/doc1.pdf" in links
    assert "https://other.test/docs/Doc%20Two.pdf" in links
    assert len(links) == 2  # duplicates removed, non-pdfs excluded


@patch("loaders.pdf_downloader.requests.get")
def test_scrape_pdf_links_raises_on_http_error(mock_get):
    mock_get.return_value = FakeResponse(text="", status_code=500)
    with pytest.raises(Exception):
        pdf_downloader.scrape_pdf_links("https://example.test")


@patch("loaders.pdf_downloader.requests.get")
def test_download_pdfs_sanitises_filename(mock_get, tmp_path: Path):
    # Provide a fake streamed PDF
    resp = FakeResponse(status_code=200, content=b"%PDF-1.4 fake")
    mock_get.return_value = resp

    urls = ["https://example.test/files/Doc%20Two.pdf"]
    results = pdf_downloader.download_pdfs(urls, dest_folder=tmp_path)

    assert len(results) == 1
    assert results[0]["error"] is None
    # "%20" is decoded to " ", then sanitised — space is allowed, but slashes/etc become _
    assert results[0]["filename"].endswith(".pdf")
    assert Path(results[0]["path"]).exists()


@patch("loaders.pdf_downloader.requests.get")
def test_download_pdfs_reports_errors(mock_get, tmp_path: Path):
    mock_get.side_effect = RuntimeError("network down")
    results = pdf_downloader.download_pdfs(
        ["https://example.test/doc.pdf"], dest_folder=tmp_path
    )
    assert len(results) == 1
    assert results[0]["path"] is None
    assert "network down" in results[0]["error"]


@patch("loaders.pdf_downloader.requests.get")
def test_download_pdfs_invokes_progress_callback(mock_get, tmp_path: Path):
    mock_get.return_value = FakeResponse(status_code=200, content=b"pdf")
    calls = []

    def cb(i, total, url):
        calls.append((i, total, url))

    pdf_downloader.download_pdfs(
        ["https://example.test/a.pdf", "https://example.test/b.pdf"],
        dest_folder=tmp_path,
        progress_callback=cb,
    )
    assert calls == [
        (0, 2, "https://example.test/a.pdf"),
        (1, 2, "https://example.test/b.pdf"),
    ]


@patch("loaders.pdf_downloader.requests.get")
def test_download_pdfs_adds_pdf_extension_when_missing(mock_get, tmp_path: Path):
    mock_get.return_value = FakeResponse(status_code=200, content=b"pdf")
    results = pdf_downloader.download_pdfs(
        ["https://example.test/download"], dest_folder=tmp_path
    )
    assert results[0]["filename"].endswith(".pdf")
