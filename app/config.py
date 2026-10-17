"""Load local configuration without moving secrets into browser state."""

from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    box_client_id: str = ""
    box_client_secret: str = ""
    box_enterprise_id: str = ""
    box_access_token: str = ""
    box_user_id: str = ""
    aws_profile: str | None = None
    aws_region: str = "us-east-2"
    bedrock_model_id: str = "us.amazon.nova-pro-v1:0"
    data_dir: Path = ROOT / ".local"
    demo_username: str = ""
    demo_password: str = field(default="", repr=False)
    allowed_hosts: tuple[str, ...] = ("localhost", "127.0.0.1")
    public_origin: str = ""
    origin_token: str = field(default="", repr=False)


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env", override=False)
    return Settings(
        box_client_id=os.getenv("BOX_CLIENT_ID", ""),
        box_client_secret=os.getenv("BOX_CLIENT_SECRET", ""),
        box_enterprise_id=os.getenv("BOX_ENTERPRISE_ID", ""),
        box_access_token=os.getenv("BOX_ACCESS_TOKEN", ""),
        box_user_id=os.getenv("BOX_USER_ID", ""),
        aws_profile=os.getenv("AWS_PROFILE") or None,
        aws_region=os.getenv("AWS_REGION", "us-east-2") or "us-east-2",
        bedrock_model_id=os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0"),
        data_dir=Path(os.getenv("REVIEW_DATA_DIR", str(ROOT / ".local"))),
        demo_username=os.getenv("ARSIA_DEMO_USERNAME", ""),
        demo_password=os.getenv("ARSIA_DEMO_PASSWORD", ""),
        allowed_hosts=tuple(host.strip().lower() for host in os.getenv("ARSIA_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host.strip()),
        public_origin=os.getenv("ARSIA_PUBLIC_ORIGIN", "").rstrip("/"),
        origin_token=os.getenv("ARSIA_ORIGIN_TOKEN", ""),
    )
