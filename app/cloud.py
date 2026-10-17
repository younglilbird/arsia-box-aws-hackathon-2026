"""Scheduled Lambda entry point for the Box-native annual review workflow."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.box_client import BoxClient
from app.config import Settings


MAX_STATE_BYTES = 128 * 1024
STATE_KEYS = {
    "status", "fingerprint", "pending_fingerprint", "completed_fingerprint",
    "failed_fingerprint", "last_changed_at", "started_at", "completed_at",
    "failed_at", "updated_at", "run_id", "report_ids", "reports",
    "source_count", "selected_count", "evidence_count", "warnings", "error",
    "stage", "progress", "discovered_count", "review_issue_count",
    "missing_information_count", "revision_performed", "reviewer_confirmed",
}
SAFE_STATUSES = {"waiting", "settling", "processing", "completed", "failed", "unchanged"}


class CloudConfigurationError(RuntimeError):
    pass


class S3Store:
    """Keep only the native scheduler's small metadata state, never source text."""

    def __init__(self, client: Any, bucket: str, key: str = "state.json") -> None:
        self.client = client
        self.bucket = bucket
        self.key = key

    def read(self) -> dict[str, Any]:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self.key)
        except self.client.exceptions.NoSuchKey:
            return {}
        with response["Body"] as body:
            data = body.read(MAX_STATE_BYTES + 1)
        if len(data) > MAX_STATE_BYTES:
            raise CloudConfigurationError("State is too large.")
        state = json.loads(data)
        self._validate(state)
        return state

    @staticmethod
    def _validate(state: Any) -> None:
        if not isinstance(state, dict) or set(state) - STATE_KEYS:
            raise CloudConfigurationError("State contains unsupported fields.")
        if "status" in state and state["status"] not in SAFE_STATUSES:
            raise CloudConfigurationError("Invalid state status.")

    def write(self, state: dict[str, Any]) -> None:
        self._validate(state)
        data = json.dumps(state, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(data) > MAX_STATE_BYTES:
            raise CloudConfigurationError("State is too large.")
        self.client.put_object(
            Bucket=self.bucket,
            Key=self.key,
            Body=data,
            ContentType="application/json",
            ServerSideEncryption="AES256",
        )


def _aws_clients(region: str) -> tuple[Any, Any]:
    session = boto3.Session(region_name=region)
    config = Config(
        retries={"mode": "adaptive", "total_max_attempts": 3},
        connect_timeout=8,
        read_timeout=30,
    )
    return session.client("secretsmanager", config=config), session.client("s3", config=config)


def _load_secret(client: Any, arn: str, region: str) -> tuple[Settings, dict[str, Any]]:
    response = client.get_secret_value(SecretId=arn)
    secret_string = response.get("SecretString")
    if not isinstance(secret_string, str):
        raise CloudConfigurationError("A JSON string secret is required.")
    secret = json.loads(secret_string)
    required = ("BOX_CLIENT_ID", "BOX_CLIENT_SECRET", "BOX_ENTERPRISE_ID")
    if not isinstance(secret, dict) or any(not isinstance(secret.get(key), str) or not secret[key].strip() for key in required):
        raise CloudConfigurationError("Required Box credentials are missing.")
    native_config = secret.get("native_config")
    if not isinstance(native_config, dict):
        raise CloudConfigurationError("Native workflow configuration is missing.")
    settings = Settings(
        box_client_id=secret["BOX_CLIENT_ID"],
        box_client_secret=secret["BOX_CLIENT_SECRET"],
        box_enterprise_id=secret["BOX_ENTERPRISE_ID"],
        box_user_id=secret.get("BOX_USER_ID", ""),
        aws_profile=None,
        aws_region=region,
        bedrock_model_id=os.environ.get("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"),
        data_dir=Path("/tmp/year-in-review"),
    )
    return settings, native_config


def _process_once(box: Any, settings: Settings, config: dict[str, Any], store: S3Store) -> dict[str, Any]:
    from app.native import process_once
    return process_once(box, settings, config, store)


def _safe_summary(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"status": "completed"}
    status = result.get("status")
    summary = {"status": status if status in SAFE_STATUSES else "completed"}
    for key in ("source_count", "selected_count", "evidence_count"):
        value = result.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            summary[key] = value
    run_id = result.get("run_id")
    if isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id):
        summary["run_id"] = run_id
    return summary


def handler(_event: Any, _context: Any) -> dict[str, Any]:
    """EventBridge polls; configuration comes only from the configured secret."""
    try:
        region = os.environ.get("AWS_REGION", "us-east-2")
        arn = os.environ.get("REVIEW_SECRET_ARN", "")
        bucket = os.environ.get("REVIEW_STATE_BUCKET", "")
        if not arn or not bucket:
            raise CloudConfigurationError("Required environment configuration is missing.")
        secrets, s3 = _aws_clients(region)
        settings, native_config = _load_secret(secrets, arn, region)
        box = BoxClient(settings)
        try:
            result = _process_once(box, settings, native_config, S3Store(s3, bucket))
        finally:
            box.http.close()
        summary = _safe_summary(result)
    except (CloudConfigurationError, ValueError, TypeError, KeyError):
        summary = {"status": "failed", "reason": "configuration_or_state"}
    except (ClientError, BotoCoreError):
        summary = {"status": "failed", "reason": "aws_service_or_permissions"}
    except Exception:
        # Do not log event payloads, secret values, file content or provider errors.
        summary = {"status": "failed", "reason": "workflow_failed"}
    if summary["status"] not in {"unchanged", "waiting", "settling"}:
        print(json.dumps(summary, separators=(",", ":")))
    if summary["status"] == "failed":
        # A fixed exception makes Lambda Errors / DLQ observable without
        # attaching a provider exception, credential or source document.
        raise RuntimeError("The Box-native annual review run failed. Check the safe workflow state and service configuration.") from None
    return summary
