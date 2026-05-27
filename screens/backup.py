import asyncio
import functools
from datetime import datetime

from textual.app import ComposeResult
from textual.widgets import Static, DataTable, Button, RichLog
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding

from services.aws_session import AwsSession
from services.backup_s3 import BackupS3Service
from services.history import OptimizationHistory


class BackupPanel(Container):
    CSS = """
    BackupPanel {
        background: $surface;
    }

    .header-box {
        height: 3;
        content-align: center middle;
        background: $primary;
        color: $text;
        text-style: bold;
    }

    #bk-main {
        height: 1fr;
    }

    #bk-left {
        width: 50;
        height: 1fr;
        border: solid $primary;
        margin: 1 0 1 1;
    }

    #bk-right {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        margin: 1 1 1 0;
    }

    #bk-left-title {
        height: 3;
        content-align: center middle;
        background: $primary-darken-2;
    }

    #bk-instance-table {
        height: 1fr;
    }

    #bk-status {
        height: 3;
        content-align: center middle;
    }

    #bk-log {
        height: 1fr;
        border: solid $accent;
        margin: 0 1;
    }

    #bk-actions {
        height: 5;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("r", "refresh_instances", "Refresh"),
        Binding("b", "backup_instance", "Backup selected"),
    ]

    def __init__(self):
        super().__init__()
        self._instances = []

    def compose(self):
        yield Static("📦 RDS Backup to S3", classes="header-box")
        yield Container(
            Horizontal(
                Vertical(
                    Static("RDS Instances", id="bk-left-title"),
                    DataTable(id="bk-instance-table"),
                    id="bk-left",
                ),
                Vertical(
                    Static(id="bk-status"),
                    RichLog(id="bk-log", highlight=True, markup=True, max_lines=200),
                    Horizontal(
                        Button("🔄 Refresh", id="bk-refresh", variant="primary"),
                        Button("📤 Export Snapshot to S3", id="bk-export", variant="error"),
                        id="bk-actions",
                    ),
                    id="bk-right",
                ),
                id="bk-main",
            ),
        )

    def on_mount(self):
        self.call_later(self.action_refresh_instances)

    def action_refresh_instances(self):
        self._log("[bold yellow]Loading RDS instances...[/bold yellow]")
        asyncio.get_event_loop().run_in_executor(None, self._load_instances)

    def _safe_call(self, fn):
        try:
            self.app.call_from_thread(fn)
        except Exception:
            pass

    def _load_instances(self):
        try:
            session = AwsSession()
            svc = BackupS3Service(session, on_log=self._on_log)
            instances = svc.list_rds_instances()
            self._safe_call(
                functools.partial(self._on_instances_loaded, instances)
            )
        except Exception as e:
            self._safe_call(
                functools.partial(self._log, f"[red]Error: {e}[/red]")
            )

    def _on_instances_loaded(self, instances):
        self._instances = instances
        table = self.query_one("#bk-instance-table", DataTable)
        table.clear()
        table.add_columns("Instance", "Engine", "Status", "Class", "Storage")
        table.zebra_stripes = True
        table.cursor_type = "row"

        for inst in instances:
            table.add_row(
                inst["identifier"],
                inst["engine"],
                inst["status"],
                inst["class"],
                f"{inst['storage_gb']} GB",
            )

        self._log(f"[green]Loaded {len(instances)} instances[/green]")
        self.query_one("#bk-status", Static).update(
            f"[bold green]{len(instances)}[/bold green] RDS instances loaded"
        )

    def action_backup_instance(self):
        table = self.query_one("#bk-instance-table", DataTable)
        if table.cursor_row is None:
            self._log("[yellow]Select an RDS instance first[/yellow]")
            return
        row_index = table.cursor_row
        inst = self._instances[row_index]
        self._log(f"[bold yellow]Fetching snapshots for {inst['identifier']}...[/bold yellow]")
        asyncio.get_event_loop().run_in_executor(
            None, self._do_export, inst,
        )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "bk-refresh":
            self.action_refresh_instances()
        elif event.button.id == "bk-export":
            self.action_backup_instance()

    def _do_export(self, inst):
        try:
            session = AwsSession()
            user = session.get_current_user()
            svc = BackupS3Service(session, on_log=self._on_log)

            snaps = svc.list_snapshots_for(inst["identifier"])
            if not snaps:
                self._safe_call(
                    functools.partial(
                        self._log,
                        f"[yellow]No snapshots found for {inst['identifier']}. "
                        f"Taking a manual snapshot first...[/yellow]"
                    )
                )
                rds = session.get_client("rds")
                snap_id = f"{inst['identifier']}-backup-{datetime.now().strftime('%Y%m%d%H%M%S')}"
                rds.create_db_snapshot(
                    DBSnapshotIdentifier=snap_id,
                    DBInstanceIdentifier=inst["identifier"],
                )
                self._safe_call(
                    functools.partial(
                        self._log,
                        f"[green]Snapshot {snap_id} created. Export will be available once complete.[/green]"
                    )
                )
                self._safe_call(
                    functools.partial(
                        self.query_one("#bk-status", Static).update,
                        f"[green]Snapshot created: {snap_id}[/green]"
                    )
                )
                history = OptimizationHistory()
                history.add_entry(
                    category=f"backup:{inst['engine']}",
                    resource_id=inst["identifier"],
                    description=f"Manual snapshot {snap_id} created (no prior snapshots)",
                    user=user,
                    savings="N/A (backup)",
                )
                return

            latest = snaps[-1]
            bucket = svc.get_backup_bucket()

            if not bucket:
                self._safe_call(
                    functools.partial(
                        self._log,
                        "[red]No S3 bucket configured. Set S3_BACKUP_BUCKET in .env[/red]"
                    )
                )
                return

            task_id = svc.export_snapshot_to_s3(
                snapshot_id=latest["id"],
                snapshot_arn=latest["arn"],
                bucket=bucket,
                identifier=inst["identifier"],
            )

            self._safe_call(
                functools.partial(
                    self.query_one("#bk-status", Static).update,
                    f"[green]Export task: {task_id}[/green]"
                )
            )

            history = OptimizationHistory()
            history.add_entry(
                category=f"backup:{inst['engine']}",
                resource_id=inst["identifier"],
                description=f"Exported snapshot {latest['id']} to s3://{bucket}/",
                user=user,
                savings="N/A (backup)",
            )

        except Exception as e:
            self._safe_call(
                functools.partial(self._log, f"[red]Error: {e}[/red]")
            )

    def _log(self, msg: str):
        log = self.query_one("#bk-log", RichLog)
        log.write(msg)

    def _on_log(self, msg: str):
        try:
            self.app.call_from_thread(functools.partial(self._log, msg))
        except Exception:
            pass
