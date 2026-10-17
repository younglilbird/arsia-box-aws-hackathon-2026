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


def test_copy_pins_selected_version_and_returns_only_safe_metadata():
    import json
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == 'POST' and request.url.path == '/2.0/files/7/copy'
        assert json.loads(request.content) == {'parent': {'id': '101'}, 'name': 'Design.docx', 'version': '88'}
        return httpx.Response(201, json={'id': '9', 'name': 'Design.docx', 'size': 40, 'extension': 'docx',
                                        'file_version': {'id': '99'}, 'parent': {'id': '101'},
                                        'expiring_embed_link': {'access_token': 'NEVER_EXPOSE_COPY_TOKEN'}})
    copied = client_with(handler).copy_file('7', '101', 'Design.docx', '88')
    assert len(seen) == 1
    assert copied['id'] == '9' and copied['url'] == 'https://app.box.com/file/9'
    assert 'NEVER_EXPOSE_COPY_TOKEN' not in str(copied)


@pytest.mark.parametrize('failure', ['server', 'network', 'invalid_json'])
def test_copy_does_not_retry_an_ambiguous_mutation(failure):
    calls = []
    def handler(request):
        calls.append(request)
        if failure == 'network':
            raise httpx.ReadTimeout('PRIVATE_PROVIDER_DETAIL', request=request)
        if failure == 'invalid_json':
            return httpx.Response(201, text='PRIVATE_PROVIDER_DETAIL')
        return httpx.Response(502, json={'message': 'PRIVATE_PROVIDER_DETAIL'})
    with pytest.raises(BoxError, match='not retried') as raised:
        client_with(handler).copy_file('7', '101', 'Design.docx', '88')
    assert len(calls) == 1
    assert raised.value.ambiguous
    assert 'PRIVATE_PROVIDER_DETAIL' not in str(raised.value)


def test_copy_conflict_is_clear_and_never_overwrites():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(409, json={'message': 'PRIVATE_PROVIDER_DETAIL'})
    with pytest.raises(BoxError, match='No file was overwritten') as raised:
        client_with(handler).copy_file('7', '101', 'Design.docx', '88')
    assert raised.value.status_code == 409
    assert len(calls) == 1


def test_copy_foreign_or_malformed_result_is_ambiguous_without_another_post():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(201, json={'id': '9', 'name': 'Design.docx', 'parent': {'id': '999'}})
    with pytest.raises(BoxError, match='not retried') as raised:
        client_with(handler).copy_file('7', '101', 'Design.docx', '88')
    assert raised.value.ambiguous and len(calls) == 1


def test_trash_file_uses_normal_delete_if_match_and_accepts_empty_204():
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == 'DELETE' and request.url.path == '/2.0/files/7'
        assert request.headers['if-match'] == '4'
        assert request.headers['authorization'] == 'Bearer test-only-token'
        return httpx.Response(204)
    assert client_with(handler).trash_file('7', '4') == {'already_absent': False}
    assert len(seen) == 1


@pytest.mark.parametrize('status', [404, 412, 502])
def test_trash_notfound_is_safe_and_failures_do_not_retry_or_leak_provider(status):
    seen = []
    def handler(request):
        seen.append(request)
        return httpx.Response(status, json={'message': 'PRIVATE_PROVIDER_DETAIL'})
    client = client_with(handler)
    if status == 404:
        assert client.trash_file('7', '4') == {'already_absent': False, 'needs_verification': True}
    else:
        with pytest.raises(BoxError) as raised:
            client.trash_file('7', '4')
        assert 'PRIVATE_PROVIDER_DETAIL' not in str(raised.value)
    assert len(seen) == 1


def test_upload_version_preserves_id_and_sends_if_match_once():
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == 'POST' and str(request.url) == 'https://upload.box.com/api/2.0/files/7/content'
        assert request.headers['if-match'] == '4'
        assert request.headers['authorization'] == 'Bearer test-only-token'
        assert b'Updated-report.docx' in request.content and b'new report bytes' in request.content
        return httpx.Response(200, json={'entries': [{'id': '7', 'name': 'Updated-report.docx'}]})
    result = client_with(handler).upload_version('7', 'Updated-report.docx', b'new report bytes', 'application/octet-stream', etag='4')
    assert result == {'id': '7', 'name': 'Updated-report.docx', 'url': 'https://app.box.com/file/7'}
    assert len(seen) == 1


@pytest.mark.parametrize('failure', ['server', 'network', 'invalid_json', 'missing_id', 'invalid_id'])
def test_initial_upload_does_not_retry_an_uncertain_creation(failure):
    seen = []
    def handler(request):
        seen.append(request)
        if failure == 'network':
            raise httpx.ReadTimeout('PRIVATE_PROVIDER_DETAIL', request=request)
        if failure == 'invalid_json':
            return httpx.Response(201, text='PRIVATE_PROVIDER_DETAIL')
        if failure == 'missing_id':
            return httpx.Response(201, json={'entries': [{'name': 'Report.docx'}]})
        if failure == 'invalid_id':
            return httpx.Response(201, json={'entries': [{'id': 'INVALID', 'name': 'Report.docx'}]})
        return httpx.Response(502, json={'message': 'PRIVATE_PROVIDER_DETAIL'})
    with pytest.raises(BoxError, match='not retried') as raised:
        client_with(handler).upload('104', 'Report.docx', b'report bytes', 'application/octet-stream')
    assert len(seen) == 1 and raised.value.ambiguous
    assert 'PRIVATE_PROVIDER_DETAIL' not in str(raised.value)


@pytest.mark.parametrize('failure', ['stale', 'server', 'network', 'foreign_id'])
def test_upload_version_failure_is_bounded_and_sanitized(failure):
    seen = []
    def handler(request):
        seen.append(request)
        if failure == 'network':
            raise httpx.ReadTimeout('PRIVATE_PROVIDER_DETAIL', request=request)
        if failure == 'foreign_id':
            return httpx.Response(200, json={'entries': [{'id': '99', 'name': 'Unexpected.docx'}]})
        return httpx.Response(412 if failure == 'stale' else 502, json={'message': 'PRIVATE_PROVIDER_DETAIL'})
    with pytest.raises(BoxError) as raised:
        client_with(handler).upload_version('7', 'Report.docx', b'bytes', 'application/octet-stream', etag='4')
    assert len(seen) == 1 and 'PRIVATE_PROVIDER_DETAIL' not in str(raised.value)
    assert raised.value.status_code == 412 if failure == 'stale' else raised.value.ambiguous
