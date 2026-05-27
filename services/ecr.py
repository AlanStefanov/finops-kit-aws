from datetime import datetime, timezone

from services.aws_session import AwsSession


class EcrService:
    def __init__(self, session: AwsSession):
        self.client = session.get_client("ecr")

    def get_unused_images(self, days_old: int = 90):
        repos = self.client.describe_repositories()
        unused = []
        now = datetime.now(timezone.utc)

        for repo in repos.get("repositories", []):
            repo_name = repo["repositoryName"]
            paginator = self.client.get_paginator("describe_images")
            pages = paginator.paginate(repositoryName=repo_name)

            for page in pages:
                for image in page.get("imageDetails", []):
                    pushed = image.get("imagePushedAt", now)
                    age = (now - pushed).days
                    if age > days_old:
                        digest = image["imageDigest"][:12]
                        tags = image.get("imageTags", ["<untagged>"])
                        unused.append({
                            "repo": repo_name,
                            "digest": digest,
                            "tags": ", ".join(tags),
                            "age_days": age,
                            "size_mb": image.get("imageSizeInBytes", 0) / 1024 / 1024,
                        })
        return unused
