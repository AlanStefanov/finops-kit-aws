from datetime import datetime, timezone

from services.aws_session import AwsSession

KEEP_TAGS = {"_latest", "_qa", "_dev", "_prod"}


class Policy:
    def __init__(self, key: str, label: str, desc: str, icon: str,
                 candidates: list, estimate_monthly: float, cols: list[str],
                 scan_fn, apply_fn):
        self.key = key
        self.label = label
        self.desc = desc
        self.icon = icon
        self.candidates = candidates
        self.estimate_monthly = estimate_monthly
        self.cols = cols
        self.scan_fn = scan_fn
        self.apply_fn = apply_fn
        self.count = len(candidates)


class PolicyEngine:
    def __init__(self, session: AwsSession, dry_run: bool = True, on_log=None):
        self.session = session
        self.dry_run = dry_run
        self.on_log = on_log or (lambda msg: None)

    def scan_all(self) -> list[Policy]:
        self.on_log("[bold yellow]Scanning all services for cleanup policies...[/bold yellow]")
        self.on_log("")

        policies = []

        policies.append(self._scan_ecr())
        policies.append(self._scan_logs())
        policies.append(self._scan_ebs_volumes())
        policies.append(self._scan_ebs_snapshots())
        policies.append(self._scan_lambda_versions())
        policies.append(self._scan_security_groups())
        policies.append(self._scan_key_pairs())
        policies.append(self._scan_iam_users())
        policies.append(self._scan_cloudformation())
        policies.append(self._scan_elastic_ips())
        policies.append(self._scan_nat_gateways())
        policies.append(self._scan_dynamodb())
        policies.append(self._scan_rds_idle())

        policies = [p for p in policies if p.count > 0]
        policies.sort(key=lambda p: p.estimate_monthly, reverse=True)

        self.on_log("")
        self.on_log(f"[bold green]Scan complete: {len(policies)} policies with resources[/bold green]")
        return policies

    def apply(self, policy: Policy):
        self.on_log(f"[bold yellow]Applying: {policy.label}[/bold yellow]")
        if not self.dry_run:
            policy.apply_fn()
        self.on_log(f"[bold green]Done: {policy.label}[/bold green]")

    # ── ECR ──────────────────────────────────────────────

    def _scan_ecr(self):
        self.on_log("ECR: scanning repositories...")
        client = self.session.get_client("ecr")
        candidates = []
        total_savings = 0

        repos = client.describe_repositories()
        for repo in repos.get("repositories", []):
            repo_name = repo["repositoryName"]
            paginator = client.get_paginator("describe_images")
            pages = paginator.paginate(repositoryName=repo_name)
            for page in pages:
                for img in page.get("imageDetails", []):
                    tags = set(img.get("imageTags", []))
                    if tags & KEEP_TAGS:
                        continue
                    size_mb = img.get("imageSizeInBytes", 0) / 1024 / 1024
                    cost = size_mb / 1024 * 0.10
                    total_savings += cost
                    candidates.append({
                        "repo": repo_name,
                        "digest": img["imageDigest"][:16],
                        "tags": ", ".join(img.get("imageTags", [])) or "<untagged>",
                        "pushed": img.get("imagePushedAt", datetime.now(timezone.utc)).strftime("%Y-%m-%d"),
                        "size_mb": round(size_mb, 2),
                    })

        def apply():
            by_repo = {}
            for c in candidates:
                by_repo.setdefault(c["repo"], []).append(c["digest"])
            for repo, digests in by_repo.items():
                self.on_log(f"  Deleting {len(digests)} from {repo}")
                try:
                    self.session.get_client("ecr").batch_delete_image(
                        repositoryName=repo,
                        imageIds=[{"imageDigest": d} for d in digests],
                    )
                except Exception as e:
                    self.on_log(f"    [red]{e}[/red]")

        self.on_log(f"  -> {len(candidates)} images (${total_savings:.2f}/month)")
        return Policy("ecr", "ECR Images", "Delete images not tagged _latest, _qa, _dev, _prod",
                      "🗑️", candidates, round(total_savings, 2),
                      ["Repo", "Digest", "Tags", "Pushed", "Size MB"], None, apply)

    # ── CloudWatch Logs ──────────────────────────────────

    def _scan_logs(self):
        self.on_log("CloudWatch Logs: scanning...")
        logs = self.session.get_client("logs")
        paginator = logs.get_paginator("describe_log_groups")
        candidates = []
        now = datetime.now(timezone.utc)

        for page in paginator.paginate():
            for group in page.get("logGroups", []):
                name = group["logGroupName"]
                creation = group.get("creationTime", 0)
                created_dt = datetime.fromtimestamp(creation / 1000, tz=timezone.utc)
                age = (now - created_dt).days
                if age > 90:
                    stored_mb = group.get("storedBytes", 0) / 1024 / 1024
                    candidates.append({
                        "name": name,
                        "age_days": age,
                        "size_mb": round(stored_mb, 2),
                    })

        def apply():
            cw = self.session.get_client("logs")
            for c in candidates:
                try:
                    cw.delete_log_group(logGroupName=c["name"])
                except Exception as e:
                    self.on_log(f"  [red]Error: {c['name']}: {e}[/red]")

        self.on_log(f"  -> {len(candidates)} groups")
        return Policy("logs", "CloudWatch Logs", "Delete log groups older than 90 days",
                      "📋", candidates, 0.0, ["Name", "Age (days)", "Size MB"], None, apply)

    # ── EBS Unattached Volumes ───────────────────────────

    def _scan_ebs_volumes(self):
        self.on_log("EBS: unattached volumes...")
        ec2 = self.session.get_client("ec2")
        vols = ec2.describe_volumes(Filters=[{"Name": "status", "Values": ["available"]}])
        candidates = []
        for vol in vols.get("Volumes", []):
            cost = vol["Size"] * 0.08
            candidates.append({
                "volume_id": vol["VolumeId"],
                "size_gb": vol["Size"],
                "type": vol["VolumeType"],
                "created": vol["CreateTime"].strftime("%Y-%m-%d"),
                "cost_monthly": round(cost, 2),
            })

        def apply():
            for c in candidates:
                try:
                    self.session.get_client("ec2").delete_volume(VolumeId=c["volume_id"])
                    self.on_log(f"  Deleted {c['volume_id']}")
                except Exception as e:
                    self.on_log(f"  [red]Error: {e}[/red]")

        savings = sum(c["cost_monthly"] for c in candidates)
        self.on_log(f"  -> {len(candidates)} volumes (${savings:.2f}/month)")
        return Policy("ebs_vols", "EBS Volumes", "Delete unattached EBS volumes",
                      "💾", candidates, round(savings, 2),
                      ["Volume ID", "Size GB", "Type", "Cost/month"], None, apply)

    # ── EBS Snapshots ────────────────────────────────────

    def _scan_ebs_snapshots(self):
        self.on_log("EBS: old snapshots...")
        ec2 = self.session.get_client("ec2")
        snaps = ec2.describe_snapshots(OwnerIds=["self"])
        candidates = []
        now = datetime.now(timezone.utc)
        for snap in snaps.get("Snapshots", []):
            age = (now - snap["StartTime"]).days
            if age > 90:
                candidates.append({
                    "snapshot_id": snap["SnapshotId"],
                    "volume": snap.get("VolumeId", "deleted"),
                    "size_gb": snap["VolumeSize"],
                    "age_days": age,
                })

        def apply():
            for c in candidates:
                try:
                    self.session.get_client("ec2").delete_snapshot(SnapshotId=c["snapshot_id"])
                except Exception as e:
                    self.on_log(f"  [red]Error: {e}[/red]")

        self.on_log(f"  -> {len(candidates)} snapshots")
        return Policy("ebs_snaps", "EBS Snapshots", "Delete snapshots older than 90 days",
                      "📸", candidates, 0.0, ["Snapshot ID", "Volume", "Size GB", "Age (days)"],
                      None, apply)

    # ── Lambda Versions ──────────────────────────────────

    def _scan_lambda_versions(self):
        self.on_log("Lambda: old versions...")
        client = self.session.get_client("lambda")
        functions = client.list_functions()
        candidates = []
        now = datetime.now(timezone.utc)

        for fn in functions.get("Functions", []):
            fn_name = fn["FunctionName"]
            versions = client.list_versions_by_function(FunctionName=fn_name)
            for ver in versions.get("Versions", []):
                if ver["Version"] == "$LATEST":
                    continue
                modified = ver["LastModified"]
                modified_dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                age = (now - modified_dt).days
                if age > 90:
                    candidates.append({
                        "function": fn_name,
                        "version": ver["Version"],
                        "age_days": age,
                        "size_mb": round(ver.get("CodeSize", 0) / 1024 / 1024, 2),
                    })

        def apply():
            for c in candidates:
                try:
                    self.session.get_client("lambda").delete_function(
                        FunctionName=f"{c['function']}:{c['version']}"
                    )
                except Exception as e:
                    self.on_log(f"  [red]Error: {e}[/red]")

        self.on_log(f"  -> {len(candidates)} old versions")
        return Policy("lambda", "Lambda Versions", "Delete function versions older than 90 days",
                      "⚡", candidates, 0.0, ["Function", "Version", "Age (days)", "Size MB"],
                      None, apply)

    # ── Security Groups ──────────────────────────────────

    def _scan_security_groups(self):
        self.on_log("EC2: unused security groups...")
        ec2 = self.session.get_client("ec2")
        sgs = ec2.describe_security_groups()
        used_nics = set()
        nics = ec2.describe_network_interfaces()
        for nic in nics.get("NetworkInterfaces", []):
            for g in nic.get("Groups", []):
                used_nics.add(g["GroupId"])

        candidates = []
        for sg in sgs.get("SecurityGroups", []):
            sg_id = sg["GroupId"]
            if sg_id not in used_nics and sg["GroupName"] != "default":
                candidates.append({
                    "sg_id": sg_id,
                    "name": sg["GroupName"],
                    "vpc": sg.get("VpcId", ""),
                    "desc": sg.get("Description", "")[:40],
                })

        def apply():
            for c in candidates:
                try:
                    self.session.get_client("ec2").delete_security_group(GroupId=c["sg_id"])
                    self.on_log(f"  Deleted {c['sg_id']} ({c['name']})")
                except Exception as e:
                    self.on_log(f"  [red]Error: {e}[/red]")

        self.on_log(f"  -> {len(candidates)} unused security groups")
        return Policy("sg", "Security Groups", "Delete security groups not attached to any ENI",
                      "🔒", candidates, 0.0, ["SG ID", "Name", "VPC", "Description"],
                      None, apply)

    # ── Key Pairs ────────────────────────────────────────

    def _scan_key_pairs(self):
        self.on_log("EC2: unused key pairs...")
        ec2 = self.session.get_client("ec2")
        kps = ec2.describe_key_pairs()
        instances = ec2.describe_instances()
        used_keys = set()
        for res in instances.get("Reservations", []):
            for inst in res.get("Instances", []):
                if inst.get("KeyName"):
                    used_keys.add(inst["KeyName"])

        candidates = []
        for kp in kps.get("KeyPairs", []):
            name = kp["KeyName"]
            if name not in used_keys:
                candidates.append({"name": name, "fingerprint": kp["KeyFingerprint"][:20]})

        def apply():
            for c in candidates:
                try:
                    self.session.get_client("ec2").delete_key_pair(KeyName=c["name"])
                    self.on_log(f"  Deleted key pair {c['name']}")
                except Exception as e:
                    self.on_log(f"  [red]Error: {e}[/red]")

        self.on_log(f"  -> {len(candidates)} unused key pairs")
        return Policy("kp", "Key Pairs", "Delete EC2 key pairs not associated with any instance",
                      "🔑", candidates, 0.0, ["Name", "Fingerprint"], None, apply)

    # ── IAM Users ────────────────────────────────────────

    def _scan_iam_users(self):
        self.on_log("IAM: inactive users...")
        iam = self.session.get_client("iam")
        users = iam.list_users()
        candidates = []
        now = datetime.now(timezone.utc)

        for user in users.get("Users", []):
            pwd_last = user.get("PasswordLastUsed")
            if pwd_last:
                age = (now - pwd_last).days
                if age > 90:
                    candidates.append({
                        "user": user["UserName"],
                        "last_used": pwd_last.strftime("%Y-%m-%d"),
                        "days_ago": age,
                    })
            else:
                created = user.get("CreateDate", now)
                age = (now - created).days
                if age > 90:
                    candidates.append({
                        "user": user["UserName"],
                        "last_used": "never",
                        "days_ago": age,
                    })

        def apply():
            for c in candidates:
                self.on_log(f"  [yellow]Dry-run: would disable {c['user']}[/yellow]")

        self.on_log(f"  -> {len(candidates)} users without recent login")
        return Policy("iam", "IAM Users", "Users without password login in >90 days",
                      "👤", candidates, 0.0, ["User", "Last login", "Days ago"],
                      None, apply)

    # ── CloudFormation ───────────────────────────────────

    def _scan_cloudformation(self):
        self.on_log("CloudFormation: stale stacks...")
        cf = self.session.get_client("cloudformation")
        stacks = cf.list_stacks(StackStatusFilter=["DELETE_FAILED", "ROLLBACK_COMPLETE"])
        candidates = []
        for stack in stacks.get("StackSummaries", []):
            candidates.append({
                "name": stack["StackName"],
                "status": stack["StackStatus"],
                "created": stack["CreationTime"].strftime("%Y-%m-%d"),
            })

        def apply():
            for c in candidates:
                try:
                    self.session.get_client("cloudformation").delete_stack(StackName=c["name"])
                    self.on_log(f"  Deleted stack {c['name']}")
                except Exception as e:
                    self.on_log(f"  [red]Error: {e}[/red]")

        self.on_log(f"  -> {len(candidates)} stale stacks")
        return Policy("cf", "CloudFormation", "Clean up DELETE_FAILED and ROLLBACK_COMPLETE stacks",
                      "📦", candidates, 0.0, ["Stack", "Status", "Created"], None, apply)

    # ── Elastic IPs ──────────────────────────────────────

    def _scan_elastic_ips(self):
        self.on_log("EC2: unassociated EIPs...")
        ec2 = self.session.get_client("ec2")
        addrs = ec2.describe_addresses()
        candidates = []
        for addr in addrs.get("Addresses", []):
            if "InstanceId" not in addr and "NetworkInterfaceId" not in addr:
                candidates.append({
                    "public_ip": addr.get("PublicIp", ""),
                    "allocation_id": addr.get("AllocationId", ""),
                    "cost_monthly": 3.60,
                })

        def apply():
            for c in candidates:
                try:
                    self.session.get_client("ec2").release_address(AllocationId=c["allocation_id"])
                    self.on_log(f"  Released {c['public_ip']}")
                except Exception as e:
                    self.on_log(f"  [red]Error: {e}[/red]")

        savings = sum(c["cost_monthly"] for c in candidates)
        self.on_log(f"  -> {len(candidates)} EIPs (${savings:.2f}/month)")
        return Policy("eip", "Elastic IPs", "Release unassociated Elastic IPs ($3.60/mo each)",
                      "🌐", candidates, round(savings, 2),
                      ["Public IP", "Allocation ID", "Cost/month"], None, apply)

    # ── NAT Gateways ─────────────────────────────────────

    def _scan_nat_gateways(self):
        self.on_log("EC2: idle NAT Gateways...")
        ec2 = self.session.get_client("ec2")
        ngws = ec2.describe_nat_gateways()
        candidates = []
        for ngw in ngws.get("NatGateways", []):
            if ngw["State"] in ("available",):
                candidates.append({
                    "nat_id": ngw["NatGatewayId"],
                    "vpc": ngw.get("VpcId", ""),
                    "state": ngw["State"],
                    "cost_monthly": 32.40,
                })

        def apply():
            for c in candidates:
                try:
                    self.session.get_client("ec2").delete_nat_gateway(NatGatewayId=c["nat_id"])
                    self.on_log(f"  Deleted {c['nat_id']}")
                except Exception as e:
                    self.on_log(f"  [red]Error: {e}[/red]")

        savings = sum(c["cost_monthly"] for c in candidates)
        self.on_log(f"  -> {len(candidates)} NAT Gateways (${savings:.2f}/month)")
        return Policy("nat", "NAT Gateways", "Delete idle NAT Gateways ($32.40/mo each)",
                      "🌐", candidates, round(savings, 2),
                      ["NAT ID", "VPC", "State", "Cost/month"], None, apply)

    # ── DynamoDB ─────────────────────────────────────────

    def _scan_dynamodb(self):
        self.on_log("DynamoDB: empty tables...")
        client = self.session.get_client("dynamodb")
        tables = client.list_tables()
        candidates = []
        for name in tables.get("TableNames", []):
            desc = client.describe_table(TableName=name)
            table = desc["Table"]
            items = table.get("ItemCount", 0)
            size_mb = round(table.get("TableSizeBytes", 0) / 1024 / 1024, 3)
            if items == 0:
                candidates.append({
                    "table": name,
                    "items": items,
                    "size_mb": size_mb,
                    "status": table.get("TableStatus", ""),
                })

        def apply():
            for c in candidates:
                try:
                    self.session.get_client("dynamodb").delete_table(TableName=c["table"])
                    self.on_log(f"  Deleted table {c['table']}")
                except Exception as e:
                    self.on_log(f"  [red]Error: {e}[/red]")

        self.on_log(f"  -> {len(candidates)} empty tables")
        return Policy("dynamo", "DynamoDB Tables", "Delete tables with 0 items",
                      "📊", candidates, 0.0, ["Table", "Items", "Size MB", "Status"],
                      None, apply)

    # ── RDS Idle ─────────────────────────────────────────

    def _scan_rds_idle(self):
        self.on_log("RDS: running instances...")
        rds = self.session.get_client("rds")
        instances = rds.describe_db_instances()
        candidates = []
        for inst in instances.get("DBInstances", []):
            if inst.get("DBInstanceStatus") != "available":
                continue
            candidates.append({
                "identifier": inst["DBInstanceIdentifier"],
                "class": inst["DBInstanceClass"],
                "engine": inst["Engine"],
                "storage_gb": inst["AllocatedStorage"],
                "multi_az": inst.get("MultiAZ", False),
            })

        def apply():
            for c in candidates:
                self.on_log(f"  [yellow]Review: {c['identifier']} ({c['class']})[/yellow]")

        self.on_log(f"  -> {len(candidates)} RDS instances")
        return Policy("rds", "RDS Instances", "Running RDS instances — review if all needed",
                      "🗄️", candidates, 0.0, ["Identifier", "Class", "Engine", "Storage"],
                      None, apply)
