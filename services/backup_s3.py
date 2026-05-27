import os
from datetime import datetime, timezone

from services.aws_session import AwsSession


class BackupS3Service:
    def __init__(self, session: AwsSession, on_log=None):
        self.session = session
        self.on_log = on_log or (lambda msg: None)

    def list_rds_instances(self):
        self.on_log("[bold]Listing RDS instances...[/bold]")
        rds = self.session.get_client("rds")
        instances = rds.describe_db_instances()
        result = []
        for inst in instances.get("DBInstances", []):
            result.append({
                "identifier": inst["DBInstanceIdentifier"],
                "engine": inst["Engine"],
                "engine_version": inst.get("EngineVersion", ""),
                "status": inst.get("DBInstanceStatus", ""),
                "class": inst["DBInstanceClass"],
                "storage_gb": inst["AllocatedStorage"],
                "multi_az": inst.get("MultiAZ", False),
                "has_snapshot": False,
            })
        self.on_log(f"  -> {len(result)} RDS instances found")
        return result

    def list_snapshots_for(self, identifier: str):
        rds = self.session.get_client("rds")
        snaps = rds.describe_db_snapshots(
            DBInstanceIdentifier=identifier,
            SnapshotType="automated",
        )
        manual = rds.describe_db_snapshots(
            DBInstanceIdentifier=identifier,
            SnapshotType="manual",
        )
        all_snaps = (
            snaps.get("DBSnapshots", [])
            + manual.get("DBSnapshots", [])
        )
        return [
            {
                "id": s["DBSnapshotIdentifier"],
                "arn": s["DBSnapshotArn"],
                "type": "manual" if s.get("SnapshotType") == "manual" else "automated",
                "created": s["SnapshotCreateTime"].strftime("%Y-%m-%d %H:%M"),
                "status": s["Status"],
                "size_gb": s["AllocatedStorage"],
                "engine": s["Engine"],
            }
            for s in all_snaps
        ]

    def get_backup_bucket(self):
        return os.environ.get(
            "S3_BACKUP_BUCKET",
            self.session.get_client("s3").list_buckets().get("Buckets", [{}])[0].get("Name", ""),
        )

    def export_snapshot_to_s3(self, snapshot_id: str, snapshot_arn: str,
                               bucket: str, identifier: str):
        self.on_log(f"[bold yellow]Exporting {snapshot_id} to s3://{bucket}/...[/bold yellow]")
        rds = self.session.get_client("rds")
        export_task_id = f"{identifier}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        try:
            response = rds.start_export_task(
                ExportTaskIdentifier=export_task_id,
                SourceArn=snapshot_arn,
                S3BucketName=bucket,
                IamRoleArn=self._get_export_role_arn(),
                KmsKeyId=self._get_export_kms_key(),
            )
            self.on_log(f"[green]Export task started: {export_task_id}[/green]")
            self.on_log(f"[green]  -> Status: {response.get('Status', 'UNKNOWN')}[/green]")
            return export_task_id
        except Exception as e:
            self.on_log(f"[red]Error starting export: {e}[/red]")
            raise

    def _get_export_role_arn(self):
        iam = self.session.get_client("iam")
        roles = iam.list_roles(PathPrefix="/service-role/")
        for role in roles.get("Roles", []):
            if "export" in role["RoleName"].lower():
                return role["Arn"]
        try:
            roles = iam.list_roles()
            for role in roles.get("Roles", []):
                if "export" in role["RoleName"].lower():
                    return role["Arn"]
        except Exception:
            pass
        return "arn:aws:iam::ACCOUNT_ID:role/default-export-role"

    def _get_export_kms_key(self):
        kms = self.session.get_client("kms")
        try:
            keys = kms.list_aliases()
            for alias in keys.get("Aliases", []):
                if "alias/aws/rds" in alias.get("AliasName", ""):
                    return alias.get("TargetKeyId", "")
        except Exception:
            pass
        return "alias/aws/rds"
