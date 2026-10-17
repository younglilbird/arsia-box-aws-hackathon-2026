#!/usr/bin/env python3
"""Populate a bootstrapped stack from local files without printing secrets.

Infrastructure is managed by infra/template.yaml. This helper only transfers
the ignored local Box configuration, private initial state and code artifact.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import load_settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack-name", default="box-annual-review-hackathon")
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / ".local" / "native-config.json")
    args = parser.parse_args()
    settings = load_settings()
    if not args.artifact.is_file():
        parser.error("The code artifact does not exist.")
    native = json.loads(args.config.read_text(encoding="utf-8"))
    from app.native import _configuration
    _configuration(native)
    credentials = {"BOX_CLIENT_ID": settings.box_client_id, "BOX_CLIENT_SECRET": settings.box_client_secret,
                   "BOX_ENTERPRISE_ID": settings.box_enterprise_id, "BOX_USER_ID": settings.box_user_id,
                   "native_config": native}
    if not all(credentials[key] for key in ("BOX_CLIENT_ID", "BOX_CLIENT_SECRET", "BOX_ENTERPRISE_ID", "BOX_USER_ID")):
        parser.error("Set the local Box application credentials and managed user ID first.")
    session = boto3.Session(profile_name=settings.aws_profile, region_name=settings.aws_region)
    config = Config(retries={"mode": "adaptive", "total_max_attempts": 3}, connect_timeout=8, read_timeout=60)
    cf = session.client("cloudformation", config=config)
    stack = cf.describe_stacks(StackName=args.stack_name)["Stacks"][0]
    outputs = {item["OutputKey"]: item["OutputValue"] for item in stack.get("Outputs", [])}
    if not {"BoxSecretArn", "StateBucketName", "WorkerName"} <= outputs.keys():
        parser.error("Wait for the infrastructure bootstrap to finish.")
    session.client("secretsmanager", config=config).put_secret_value(
        SecretId=outputs["BoxSecretArn"], SecretString=json.dumps(credentials))
    s3 = session.client("s3", config=config)
    key = "artifacts/native-" + hashlib.sha256(args.artifact.read_bytes()).hexdigest()[:16] + ".zip"
    s3.upload_file(str(args.artifact), outputs["StateBucketName"], key,
                   ExtraArgs={"ServerSideEncryption": "AES256", "ContentType": "application/zip"})
    # Never overwrite existing state during code updates.
    try:
        s3.head_object(Bucket=outputs["StateBucketName"], Key="state.json")
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in {"404", "NoSuchKey", "NotFound"}:
            raise
        s3.put_object(Bucket=outputs["StateBucketName"], Key="state.json", Body=b"{}",
                      ContentType="application/json", ServerSideEncryption="AES256")
    result = {"stack_name": args.stack_name, "artifact_key": key, "worker_name": outputs["WorkerName"],
              "state_bucket": outputs["StateBucketName"], "secret_configured": True,
              "native_box_url": "https://app.box.com/folder/" + native["root_folder_id"]}
    path = ROOT / ".local" / "deployment.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    path.chmod(0o600)
    print(json.dumps(result, indent=2))
    return 0


def entry():
    try:
        return main()
    except (ClientError, BotoCoreError):
        print("AWS configuration transfer failed. Check the authenticated profile and stack permissions.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(entry())
