import os
import configparser

import boto3


def _is_placeholder(val: str) -> bool:
    lowered = val.lower().replace("-", "").replace("_", "")
    return (
        "xxx" in lowered
        or "xxxx" in val
        or val.startswith("AKIA") and val.endswith("XXXXXXX")
    )


def load_env_file(env_path: str = None):
    if env_path is None:
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if val and not _is_placeholder(val):
                os.environ.setdefault(key, val)


class AwsSession:
    def __init__(self, profile: str = "default"):
        load_env_file()
        aws_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".aws")
        cred_path = os.path.join(aws_dir, "credentials")
        cfg_path = os.path.join(aws_dir, "config")

        self.session = None

        env_key = os.environ.get("AWS_ACCESS_KEY_ID")
        env_secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
        env_region = os.environ.get("AWS_DEFAULT_REGION")
        env_profile = os.environ.get("AWS_PROFILE", profile)

        if env_key and env_secret:
            self.session = boto3.Session(
                aws_access_key_id=env_key,
                aws_secret_access_key=env_secret,
                region_name=env_region or "us-east-1",
            )
        else:
            self._load_legacy(cred_path, cfg_path, env_profile)

    def _load_legacy(self, cred_path: str, cfg_path: str, profile: str):
        creds = configparser.ConfigParser()
        creds.read(cred_path)
        cfg = configparser.ConfigParser()
        cfg.read(cfg_path)

        region = cfg.get(profile, "region", fallback="us-east-1")
        key = creds.get(profile, "aws_access_key_id", fallback=None)
        secret = creds.get(profile, "aws_secret_access_key", fallback=None)

        if key and secret:
            self.session = boto3.Session(
                aws_access_key_id=key,
                aws_secret_access_key=secret,
                region_name=region,
            )
        else:
            self.session = boto3.Session(region_name=region)

    def get_client(self, service: str):
        return self.session.client(service)

    def get_current_user(self) -> str:
        sts = self.session.client("sts")
        caller = sts.get_caller_identity()
        arn = caller.get("Arn", "unknown")
        parts = arn.split("/")
        name = parts[-1] if len(parts) > 1 else parts[0].split(":")[-1]
        return name if name else "unknown"
