from datetime import datetime, timezone

from services.aws_session import AwsSession


class S3Service:
    def __init__(self, session: AwsSession):
        self.client = session.get_client("s3")

    def get_old_objects(self, days_old: int = 90):
        buckets = self.client.list_buckets()
        old_objects = []
        now = datetime.now(timezone.utc)

        for bucket in buckets.get("Buckets", []):
            name = bucket["Name"]
            try:
                paginator = self.client.get_paginator("list_objects_v2")
                pages = paginator.paginate(Bucket=name)

                for page in pages:
                    if "Contents" not in page:
                        continue
                    for obj in page["Contents"]:
                        last_mod = obj["LastModified"]
                        age = (now - last_mod).days
                        if age > days_old:
                            old_objects.append({
                                "bucket": name,
                                "key": obj["Key"],
                                "size_mb": obj["Size"] / 1024 / 1024,
                                "age_days": age,
                            })
            except Exception:
                pass
        return old_objects

    def get_bucket_sizes(self):
        buckets = self.client.list_buckets()
        sizes = []

        for bucket in buckets.get("Buckets", []):
            name = bucket["Name"]
            total_size = 0
            total_objects = 0
            try:
                paginator = self.client.get_paginator("list_objects_v2")
                pages = paginator.paginate(Bucket=name)
                for page in pages:
                    if "Contents" not in page:
                        continue
                    for obj in page["Contents"]:
                        total_size += obj["Size"]
                        total_objects += 1
                sizes.append({
                    "bucket": name,
                    "size_gb": total_size / 1024 / 1024 / 1024,
                    "objects": total_objects,
                })
            except Exception:
                sizes.append({"bucket": name, "size_gb": 0, "objects": 0})
        return sizes
