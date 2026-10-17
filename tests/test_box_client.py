from io import BytesIO

import httpx
import pytest

from app.box_client import BoxClient, BoxError, extract_text
from app.config import Settings


def client_with(handler):
    client = BoxClient(Settings(box_access_token="test-only-token"))
    client.http = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
    return client


def test_download_removes_authorization_on_boxcloud_redirect():
    seen = []
    def handler(request):
        seen.append((request.url.host, request.headers.get("authorization")))
        if request.url.host == "api.box.com":
            assert request.url.params["version"] == "88"
            return httpx.Response(302, headers={"location": "https://dl.boxcloud.com/safe-content"})
        return httpx.Response(200, content=b"source content")
    client = client_with(handler)
    assert client.download({"id": "7", "file_version": {"id": "88"}}) == b"source content"
    assert seen == [("api.box.com", "Bearer test-only-token"), ("dl.boxcloud.com", None)]


def test_download_rejects_external_redirect():
    client = client_with(lambda _: httpx.Response(302, headers={"location": "https://example.com/steal"}))
    with pytest.raises(BoxError, match="domains"):
        client.download({"id": "7"})


def test_folder_marker_pagination_and_recursive_limit_are_visible():
    def handler(request):
        if not request.url.path.endswith("items"):
            return httpx.Response(200, json={"id": "0", "name": "Root"})
        if "marker" not in request.url.params:
            return httpx.Response(200, json={"entries": [{"id": "1", "name": "one.txt", "type": "file", "size": 30}], "next_marker": "next"})
        return httpx.Response(200, json={"entries": [{"id": "2", "name": "two.md", "type": "file", "size": 40}, {"id": "3", "name": "image.png", "type": "file", "size": 40}]})
    result = client_with(handler).discover("0", max_files=1)
    assert len(result["files"]) == 1
    assert result["discovered"] == 3
    assert result["truncated"] is True
    assert len(result["skipped"]) == 2


def test_ccg_refreshes_after_unauthorized_without_exposing_secret():
    calls = []
    def handler(request):
        calls.append(request)
        if request.url.path == "/oauth2/token":
            n = sum(c.url.path == "/oauth2/token" for c in calls)
            return httpx.Response(200, json={"access_token": f"token{n}", "expires_in": 3600})
        if request.headers["authorization"] == "Bearer token1":
            return httpx.Response(401)
        return httpx.Response(200, json={"id": "1", "name": "Service account"})
    client = BoxClient(Settings(box_client_id="id", box_client_secret="secret", box_enterprise_id="12"))
    client.http = httpx.Client(transport=httpx.MockTransport(handler))
    assert client.identity()["name"] == "Service account"
    assert sum(c.url.path == "/oauth2/token" for c in calls) == 2


def test_read_chinese_and_office_tables():
    assert extract_text("Annual self-review".encode("utf-8"), "txt") == "Annual self-review"
    from docx import Document
    document = Document()
    document.add_paragraph("Project Atlas")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Measured improvement"
    table.cell(0, 1).text = "20%"
    output = BytesIO()
    document.save(output)
    text = extract_text(output.getvalue(), "docx")
    assert "Project Atlas" in text and "20%" in text
