from datetime import datetime, timezone

from services.aws_session import AwsSession


class CleanupService:
    def __init__(self, session: AwsSession):
        self.ec2 = session.get_client("ec2")
        self.rds = session.get_client("rds")
        self.elb = session.get_client("elbv2")
        self.elb_classic = session.get_client("elb")
        self.lambda_client = session.get_client("lambda")
        self.cloudfront = session.get_client("cloudfront")
        self.dynamodb = session.get_client("dynamodb")
        self.elasticache = session.get_client("elasticache")
        self.nat = session.get_client("ec2")

    def scan_all(self):
        return {
            "elastic_ips": self._unassociated_elastic_ips(),
            "unattached_ebs": self._unattached_ebs_volumes(),
            "old_ebs_snapshots": self._old_ebs_snapshots(),
            "idle_rds": self._idle_rds_instances(),
            "unused_load_balancers": self._unused_load_balancers(),
            "old_lambda_versions": self._old_lambda_versions(),
            "unused_cloudfront": self._unused_cloudfront_distributions(),
            "underutilized_dynamodb": self._underutilized_dynamodb(),
            "idle_elasticache": self._idle_elasticache(),
            "unused_nat_gateways": self._unused_nat_gateways(),
        }

    def _unassociated_elastic_ips(self):
        addrs = self.ec2.describe_addresses()
        ips = []
        for addr in addrs.get("Addresses", []):
            if "InstanceId" not in addr and "NetworkInterfaceId" not in addr:
                ips.append({
                    "public_ip": addr.get("PublicIp", ""),
                    "allocation_id": addr.get("AllocationId", ""),
                    "cost_monthly": 3.60,
                })
        return ips

    def _unattached_ebs_volumes(self):
        vols = self.ec2.describe_volumes(Filters=[{"Name": "status", "Values": ["available"]}])
        result = []
        for vol in vols.get("Volumes", []):
            size_gb = vol["Size"]
            cost = size_gb * 0.08
            result.append({
                "volume_id": vol["VolumeId"],
                "size_gb": size_gb,
                "type": vol["VolumeType"],
                "cost_monthly": round(cost, 2),
                "created": vol["CreateTime"].strftime("%Y-%m-%d"),
            })
        return result

    def _old_ebs_snapshots(self, days: int = 90):
        snaps = self.ec2.describe_snapshots(OwnerIds=["self"])
        old = []
        now = datetime.now(timezone.utc)
        for snap in snaps.get("Snapshots", []):
            age = (now - snap["StartTime"]).days
            if age > days:
                old.append({
                    "snapshot_id": snap["SnapshotId"],
                    "volume_id": snap.get("VolumeId", "deleted"),
                    "size_gb": snap["VolumeSize"],
                    "age_days": age,
                    "start_time": snap["StartTime"].strftime("%Y-%m-%d"),
                })
        return old

    def _idle_rds_instances(self):
        instances = self.rds.describe_db_instances()
        idle = []
        for inst in instances.get("DBInstances", []):
            if inst.get("DBInstanceStatus") != "available":
                continue
            idle.append({
                "identifier": inst["DBInstanceIdentifier"],
                "class": inst["DBInstanceClass"],
                "engine": inst["Engine"],
                "storage_gb": inst["AllocatedStorage"],
                "multi_az": inst.get("MultiAZ", False),
                "cost_estimate": "varies",
            })
        return idle

    def _unused_load_balancers(self):
        unused = []

        lbs = self.elb.describe_load_balancers()
        for lb in lbs.get("LoadBalancers", []):
            arn = lb["LoadBalancerArn"]
            tgs = self.elb.describe_target_groups(LoadBalancerArn=arn)
            has_targets = False
            for tg in tgs.get("TargetGroups", []):
                tg_arn = tg["TargetGroupArn"]
                health = self.elb.describe_target_health(TargetGroupArn=tg_arn)
                for desc in health.get("TargetHealthDescriptions", []):
                    if desc["TargetHealth"]["State"] == "healthy":
                        has_targets = True
                        break
                if has_targets:
                    break
            if not has_targets:
                unused.append({
                    "name": lb["LoadBalancerName"],
                    "type": lb["Type"],
                    "state": lb["State"]["Code"],
                    "created": lb["CreatedTime"].strftime("%Y-%m-%d"),
                })

        classic = self.elb_classic.describe_load_balancers()
        for lb in classic.get("LoadBalancerDescriptions", []):
            instances = lb.get("Instances", [])
            if not instances:
                unused.append({
                    "name": lb["LoadBalancerName"],
                    "type": "classic",
                    "state": "no_instances",
                    "created": lb["CreatedTime"].strftime("%Y-%m-%d"),
                })

        return unused

    def _old_lambda_versions(self, days: int = 90):
        functions = self.lambda_client.list_functions()
        old_versions = []
        now = datetime.now(timezone.utc)

        for fn in functions.get("Functions", []):
            fn_name = fn["FunctionName"]
            versions = self.lambda_client.list_versions_by_function(FunctionName=fn_name)
            total_size = 0
            count = 0
            for ver in versions.get("Versions", []):
                if ver["Version"] == "$LATEST":
                    continue
                modified = ver["LastModified"]
                modified_dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                age = (now - modified_dt).days
                if age > days:
                    total_size += ver.get("CodeSize", 0)
                    count += 1
            if count > 0:
                old_versions.append({
                    "function": fn_name,
                    "old_versions": count,
                    "total_size_mb": round(total_size / 1024 / 1024, 2),
                    "runtime": fn.get("Runtime", "unknown"),
                })
        return old_versions

    def _unused_cloudfront_distributions(self):
        dists = self.cloudfront.list_distributions()
        unused = []
        items = (dists.get("DistributionList") or {}).get("Items", [])
        for dist in items:
            if not dist.get("Enabled", False):
                unused.append({
                    "id": dist["Id"],
                    "domain": dist.get("DomainName", ""),
                    "status": dist.get("Status", ""),
                    "enabled": dist.get("Enabled", False),
                })
        return unused

    def _underutilized_dynamodb(self):
        tables = self.dynamodb.list_tables()
        result = []
        for name in tables.get("TableNames", []):
            desc = self.dynamodb.describe_table(TableName=name)
            table = desc["Table"]
            item_count = table.get("ItemCount", 0)
            size_bytes = table.get("TableSizeBytes", 0)
            result.append({
                "table": name,
                "items": item_count,
                "size_mb": round(size_bytes / 1024 / 1024, 3),
                "status": table.get("TableStatus", ""),
            })
        return result

    def _idle_elasticache(self):
        clusters = self.elasticache.describe_cache_clusters()
        idle = []
        for cluster in clusters.get("CacheClusters", []):
            if cluster.get("CacheClusterStatus") != "available":
                continue
            idle.append({
                "cluster_id": cluster["CacheClusterId"],
                "engine": cluster["Engine"],
                "node_type": cluster["CacheNodeType"],
                "num_nodes": cluster.get("NumCacheNodes", 1),
                "status": cluster["CacheClusterStatus"],
            })
        return idle

    def _unused_nat_gateways(self):
        nat_gws = self.nat.describe_nat_gateways()
        unused = []
        for ngw in nat_gws.get("NatGateways", []):
            if ngw["State"] in ("available",):
                unused.append({
                    "nat_id": ngw["NatGatewayId"],
                    "state": ngw["State"],
                    "vpc": ngw.get("VpcId", ""),
                    "cost_monthly": 32.40,
                })
        return unused
