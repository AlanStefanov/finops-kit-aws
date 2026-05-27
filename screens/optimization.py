import asyncio
import functools

from textual.app import ComposeResult
from textual.widgets import Static, Tree, DataTable
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding

from services.aws_session import AwsSession
from services.cleanup import CleanupService
from services.history import OptimizationHistory


class OptimizationPanel(Container):
    CSS = """
    OptimizationPanel {
        background: $surface;
    }

    .header-box {
        height: 3;
        content-align: center middle;
        background: $warning;
        color: $text;
        text-style: bold;
    }

    #main-container {
        height: 1fr;
    }

    #nav-tree {
        width: 36;
        height: 1fr;
        border: solid $primary;
        margin: 1 0 1 1;
    }

    #detail-panel {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        margin: 1 1 1 0;
    }

    #detail-title {
        height: 3;
        content-align: center middle;
        background: $primary-darken-2;
    }

    #detail-table {
        height: 1fr;
    }

    #summary-bar {
        height: 3;
        content-align: center middle;
        background: $panel;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("l", "log_action", "Log selected"),
        Binding("enter", "select_row", "Select row"),
    ]

    def compose(self):
        yield Static("Cost Optimization Scanner", classes="header-box")
        yield Container(
            Horizontal(
                Tree("Services", id="nav-tree"),
                Vertical(
                    Static("Select a category to view details", id="detail-title"),
                    DataTable(id="detail-table"),
                    id="detail-panel",
                ),
                id="main-container",
            ),
        )
        yield Static("Press [bold]R[/bold] to scan AWS resources for cleanup opportunities.", id="summary-bar")

    def on_mount(self):
        self.call_later(self.refresh_data)

    def _safe_call(self, fn):
        try:
            self.app.call_from_thread(fn)
        except Exception:
            pass

    def action_log_action(self):
        table = self.query_one("#detail-table", DataTable)
        title = self.query_one("#detail-title", Static)
        if table.cursor_row is None:
            self.query_one("#summary-bar", Static).update("[yellow]Select a row first[/yellow]")
            return

        row_index = table.cursor_row
        row = table.get_row_at(row_index)
        if not row:
            return

        resource_id = str(row[0])
        title_text = str(title.renderable)
        desc = f"{title_text} - {resource_id}"

        session = AwsSession()
        user = session.get_current_user()

        history = OptimizationHistory()
        history.add_entry(
            category=title_text,
            resource_id=resource_id,
            description=desc,
            user=user,
        )
        self.query_one("#summary-bar", Static).update(
            f"[green]Logged: {title_text} -> {resource_id} (by {user})[/green]"
        )

    def action_select_row(self):
        self.action_log_action()

    def on_tree_node_selected(self, event: Tree.NodeSelected):
        node = event.node
        if not node.data:
            return

        key = node.data["key"]
        items = node.data["items"]
        title = self.query_one("#detail-title", Static)
        table = self.query_one("#detail-table", DataTable)
        table.clear()

        renderers = {
            "elastic_ips": (
                "Unassociated Elastic IPs",
                ["Public IP", "Monthly Cost"],
                [lambda i: (i["public_ip"], f"${i['cost_monthly']:.2f}")]
            ),
            "unattached_ebs": (
                "Unattached EBS Volumes",
                ["Volume ID", "Size (GB)", "Type", "Cost/Month"],
                [lambda i: (i["volume_id"], str(i["size_gb"]), i["type"], f"${i['cost_monthly']:.2f}")]
            ),
            "old_ebs_snapshots": (
                "Old EBS Snapshots (>90 days)",
                ["Snapshot ID", "Volume", "Size (GB)", "Age (days)"],
                [lambda i: (i["snapshot_id"], i["volume_id"], str(i["size_gb"]), str(i["age_days"]))]
            ),
            "idle_rds": (
                "RDS Instances",
                ["Identifier", "Class", "Engine", "Storage"],
                [lambda i: (i["identifier"], i["class"], i["engine"], f"{i['storage_gb']} GB")]
            ),
            "unused_load_balancers": (
                "Unused Load Balancers",
                ["Name", "Type", "State"],
                [lambda i: (i["name"], i["type"], i["state"])]
            ),
            "old_lambda_versions": (
                "Old Lambda Versions (>90 days)",
                ["Function", "Old Versions", "Size (MB)", "Runtime"],
                [lambda i: (i["function"], str(i["old_versions"]), str(i["total_size_mb"]), i["runtime"])]
            ),
            "unused_cloudfront": (
                "Disabled CloudFront Distributions",
                ["ID", "Domain", "Status"],
                [lambda i: (i["id"], i["domain"], i["status"])]
            ),
            "underutilized_dynamodb": (
                "DynamoDB Tables",
                ["Table", "Items", "Size (MB)", "Status"],
                [lambda i: (i["table"], str(i["items"]), str(i["size_mb"]), i["status"])]
            ),
            "idle_elasticache": (
                "ElastiCache Clusters",
                ["Cluster ID", "Engine", "Node Type", "Nodes"],
                [lambda i: (i["cluster_id"], i["engine"], i["node_type"], str(i["num_nodes"]))]
            ),
            "unused_nat_gateways": (
                "NAT Gateways (idle)",
                ["NAT Gateway ID", "State", "VPC", "Cost/Month"],
                [lambda i: (i["nat_id"], i["state"], i["vpc"], f"${i['cost_monthly']:.2f}")]
            ),
        }

        if key in renderers:
            label, cols, row_fns = renderers[key]
            title.update(f"{label} ({len(items)})")
            table.add_columns(*cols)
            table.cursor_type = "row"
            table.zebra_stripes = True
            for item in items:
                table.add_row(*row_fns[0](item))

    def refresh_data(self):
        summary = self.query_one("#summary-bar", Static)
        summary.update("[bold yellow]Scanning all AWS services...[/bold yellow]")

        tree = self.query_one("#nav-tree", Tree)
        tree.clear()

        asyncio.get_event_loop().run_in_executor(None, self._run_scan)

    def _run_scan(self):
        try:
            session = AwsSession()
            cleanup = CleanupService(session)
            data = cleanup.scan_all()
            self._safe_call(
                functools.partial(self._on_scan_complete, data)
            )
        except Exception as e:
            self._safe_call(
                functools.partial(
                    self.query_one("#summary-bar", Static).update,
                    f"[red]Error: {e}[/red]"
                )
            )

    def _on_scan_complete(self, data):
        tree = self.query_one("#nav-tree", Tree)
        tree.clear()

        categories = {
            "elastic_ips": ("Elastic IPs", "🌐"),
            "unattached_ebs": ("EBS Volumes (unattached)", "💾"),
            "old_ebs_snapshots": ("EBS Snapshots (old)", "📸"),
            "idle_rds": ("RDS Instances", "🗄"),
            "unused_load_balancers": ("Load Balancers (unused)", "⚖"),
            "old_lambda_versions": ("Lambda Versions (old)", "⚡"),
            "unused_cloudfront": ("CloudFront (disabled)", "🌍"),
            "underutilized_dynamodb": ("DynamoDB Tables", "📊"),
            "idle_elasticache": ("ElastiCache Clusters", "🔴"),
            "unused_nat_gateways": ("NAT Gateways", "🌐"),
        }

        top_key = None
        top_count = 0
        total_items = 0

        for key, (label, icon) in categories.items():
            items = data.get(key, [])
            count = len(items)
            total_items += count
            if count > top_count:
                top_count = count
                top_key = key
            node = tree.root.add(f"{icon} {label} [bold]({count})[/bold]")
            node.data = {"key": key, "items": items}
            node.allow_expand = False

        tree.root.expand()

        detail_title = self.query_one("#detail-title", Static)
        detail_title.update("Select a category to view details")

        summary = self.query_one("#summary-bar", Static)
        summary.update(
            f"[bold green]Scan complete![/bold green] Found [bold]{total_items}[/bold] "
            f"resources that may need attention."
        )

        if top_key and top_count > 0:
            for child in tree.root.children:
                if child.data and child.data.get("key") == top_key:
                    tree.select_node(child)
                    self.on_tree_node_selected(
                        Tree.NodeSelected(tree, child)
                    )
                    break
