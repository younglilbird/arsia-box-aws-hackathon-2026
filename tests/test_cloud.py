import io
import json
import unittest
from unittest.mock import MagicMock, patch

from app.cloud import CloudConfigurationError, S3Store, handler


class CloudStoreTests(unittest.TestCase):
    def test_missing_state_is_empty_and_other_errors_do_not_reset_state(self):
        class NoSuchKey(Exception):
            pass
        client = MagicMock()
        client.exceptions.NoSuchKey = NoSuchKey
        client.get_object.side_effect = NoSuchKey()
        self.assertEqual(S3Store(client, "state-bucket").read(), {})
        client.get_object.side_effect = RuntimeError("access denied")
        with self.assertRaises(RuntimeError):
            S3Store(client, "state-bucket").read()

    def test_stream_closes_and_state_is_encrypted(self):
        client = MagicMock()
        body = io.BytesIO(b'{"status":"completed","source_count":8}')
        client.get_object.return_value = {"Body": body}
        store = S3Store(client, "state-bucket")
        state = store.read()
        self.assertTrue(body.closed)
        store.write(state)
        kwargs = client.put_object.call_args.kwargs
        self.assertEqual(kwargs["ServerSideEncryption"], "AES256")
        self.assertEqual(kwargs["Key"], "state.json")
        self.assertEqual(json.loads(kwargs["Body"]), state)

    def test_raw_sources_and_credentials_are_not_permitted_state_fields(self):
        client = MagicMock()
        for field in ("sources", "evidence", "report_markdown", "BOX_CLIENT_SECRET"):
            with self.assertRaises(CloudConfigurationError):
                S3Store(client, "state-bucket").write({field: "must not persist"})
        client.put_object.assert_not_called()


class CloudHandlerTests(unittest.TestCase):
    def test_handler_uses_secret_config_ignores_event_and_returns_safe_metadata(self):
        secrets, s3 = MagicMock(), MagicMock()
        secrets.get_secret_value.return_value = {"SecretString": json.dumps({
            "BOX_CLIENT_ID": "id", "BOX_CLIENT_SECRET": "secret-value", "BOX_ENTERPRISE_ID": "enterprise",
            "BOX_USER_ID": "user", "native_config": {"root_folder_id": "123"},
        })}
        with patch.dict("os.environ", {"REVIEW_SECRET_ARN": "secret-arn", "REVIEW_STATE_BUCKET": "state-bucket", "AWS_REGION": "us-east-2"}), patch("app.cloud._aws_clients", return_value=(secrets, s3)), patch("app.cloud.BoxClient") as box_type, patch("app.cloud._process_once", return_value={"status": "completed", "run_id": "run-123", "evidence_count": 38, "secret": "must-not-return"}) as process, patch("builtins.print") as log:
            summary = handler({"native_config": {"root_folder_id": "attacker-folder"}}, None)
        self.assertEqual(process.call_args.args[2], {"root_folder_id": "123"})
        self.assertIsNone(process.call_args.args[1].aws_profile)
        self.assertEqual(summary, {"status": "completed", "run_id": "run-123", "evidence_count": 38})
        self.assertNotIn("secret-value", str(log.call_args))
        box_type.return_value.http.close.assert_called_once()


class NativeS3ContractTests(unittest.TestCase):
    def test_settle_generate_and_unchanged_use_real_s3_store_contract(self):
        from app.native import process_once

        class NoSuchKey(Exception):
            pass

        class S3:
            exceptions = type("Exceptions", (), {"NoSuchKey": NoSuchKey})

            def __init__(self):
                self.data = None
                self.writes = []

            def get_object(self, **kwargs):
                if self.data is None:
                    raise NoSuchKey()
                return {"Body": io.BytesIO(self.data)}

            def put_object(self, **kwargs):
                self.data = kwargs["Body"]
                self.writes.append(kwargs)

        class Box:
            def __init__(self):
                self.uploads = []

            def list_folder(self, folder_id):
                entries = [{"type": "file", "id": "10", "name": "Project.docx", "size": 100, "file_version": {"id": "11"}}] if folder_id == "2" else []
                return {"entries": entries, "truncated": False}

            def request(self, *args, **kwargs):
                return {}

            def upload(self, folder_id, name, data, mime):
                self.uploads.append(name)
                return {"id": str(100 + len(self.uploads))}

        config = {"root_folder_id": "1", "category_folders": {"Projects": "2", "Peer Feedback": "3", "Annual Plans": "4"}, "reports_folder_id": "5", "employee_name": "Alex Chen", "year": 2026, "language": "en"}
        s3, box = S3(), Box()
        store = S3Store(s3, "state-bucket")
        workflow = MagicMock(return_value={"report_markdown": "PRIVATE REPORT CONTENT", "sources": [{"id": "10", "text": "PRIVATE SOURCE CONTENT"}], "evidence": [], "review": {"issues": [], "revision_performed": False}, "coverage": {}, "missing_information": []})
        first = process_once(box, None, config, store, workflow=workflow, clock=lambda: 100)
        self.assertEqual(first["status"], "settling")
        workflow.assert_not_called()
        with patch("app.native.make_export", return_value=(b"file", "draft.docx", "application/octet-stream")):
            second = process_once(box, None, config, store, workflow=workflow, clock=lambda: 121)
        self.assertEqual(second["status"], "completed")
        self.assertEqual(second["progress"], 100)
        self.assertFalse(second["reviewer_confirmed"])
        self.assertEqual(len(second["reports"]), 3)
        self.assertEqual(process_once(box, None, config, store, workflow=workflow, clock=lambda: 180)["status"], "unchanged")
        workflow.assert_called_once()
        self.assertNotIn(b"PRIVATE SOURCE", s3.data)
        self.assertNotIn(b"PRIVATE REPORT", s3.data)
        self.assertTrue(all(item["ServerSideEncryption"] == "AES256" for item in s3.writes))

    def test_secret_errors_do_not_disclose_values_and_idle_polls_are_quiet(self):
        with patch.dict("os.environ", {"REVIEW_SECRET_ARN": "secret-arn", "REVIEW_STATE_BUCKET": "state-bucket"}), patch("app.cloud._aws_clients", side_effect=RuntimeError("secret-value provider detail")), patch("builtins.print") as log:
            with self.assertRaisesRegex(RuntimeError, "Box-native annual review run failed") as caught:
                handler({}, None)
        self.assertTrue(caught.exception.__suppress_context__)
        self.assertEqual(json.loads(log.call_args.args[0]), {"status": "failed", "reason": "workflow_failed"})
        self.assertNotIn("secret-value", str(log.call_args))
        self.assertNotIn("secret-value", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
