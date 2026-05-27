from datetime import datetime, timezone

from services.aws_session import AwsSession


class CloudWatchService:
    def __init__(self, session: AwsSession):
        self.logs = session.get_client("logs")

    def get_stale_log_groups(self, days_old: int = 90):
        paginator = self.logs.get_paginator("describe_log_groups")
        stale = []
        now = datetime.now(timezone.utc)

        for page in paginator.paginate():
            for group in page.get("logGroups", []):
                name = group["logGroupName"]
                stored_bytes = group.get("storedBytes", 0)
                last_event = group.get("creationTime", 0)
                last_event_dt = datetime.fromtimestamp(last_event / 1000, tz=timezone.utc)
                age = (now - last_event_dt).days

                if age > days_old:
                    stale.append({
                        "name": name,
                        "size_mb": stored_bytes / 1024 / 1024,
                        "age_days": age,
                    })
        return stale
