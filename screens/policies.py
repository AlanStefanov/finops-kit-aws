import asyncio
import functools
from textual.app import ComposeResult
from textual.widgets import Static, Tree, DataTable, Button, RichLog
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding
from textual.screen import ModalScreen

from services.aws_session import AwsSession
from services.policies import PolicyEngine


class ConfirmScreen(ModalScreen):
    CSS = """
    ConfirmScreen {
        align: center middle;
    }

    #confirm-box {
        width: 54;
        height: 12;
        border: solid $warning;
        padding: 1 2;
        background: $surface;
    }

    #confirm-box > Static {
        height: 2;
        content-align: center middle;
    }

    #confirm-hint {
        height: 2;
        content-align: center middle;
        color: $text-muted;
    }

    #confirm-buttons {
        height: 3;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(self, label: str, count: int, savings: str):
        super().__init__()
        self.label = label
        self.count = count
        self.savings = savings

    def compose(self):
        yield Container(
            Static(f"[bold]Apply: {self.label}[/bold]"),
            Static(f"Will affect [red]{self.count}[/red] resources — [green]{self.savings}[/green]"),
            Static("Press [bold]Enter[/bold] to confirm or [bold]Esc[/bold] to cancel", id="confirm-hint"),
            Horizontal(
                Button("✅ Apply", variant="error", id="confirm-yes"),
                Button("❌ Cancel", variant="primary", id="confirm-no"),
                id="confirm-buttons",
            ),
            id="confirm-box",
        )

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "confirm-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def on_key(self, event):
        if event.key == "enter":
            self.dismiss(True)
        elif event.key == "escape":
            self.dismiss(False)


class PoliciesPanel(Container):
    CSS = """
    PoliciesPanel {
        background: $surface;
    }

    .header-box {
        height: 3;
        content-align: center middle;
        background: $accent;
        color: $text;
        text-style: bold;
    }

    #pol-main {
        height: 1fr;
    }

    #pol-tree {
        width: 38;
        height: 1fr;
        border: solid $primary;
        margin: 1 0 1 1;
    }

    #pol-detail {
        width: 1fr;
        height: 1fr;
        border: solid $primary;
        margin: 1 1 1 0;
    }

    #pol-title {
        height: 3;
        content-align: center middle;
        background: $primary-darken-2;
    }

    #pol-savings {
        height: 3;
        content-align: center middle;
        color: $success;
    }

    #pol-table {
        height: 1fr;
    }

    #pol-log {
        height: 8;
        border: solid $accent;
    }

    #pol-actions {
        height: 5;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }

    #pol-summary {
        height: 3;
        content-align: center middle;
        background: $panel;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("r", "refresh", "Refresh scan"),
    ]

    def __init__(self):
        super().__init__()
        self._policies = []

    def compose(self):
        yield Static("Dynamic Optimization Policies", classes="header-box")
        yield Container(
            Horizontal(
                Tree("Policies (sorted by savings)", id="pol-tree"),
                Vertical(
                    Static("Select a policy", id="pol-title"),
                    Static(id="pol-savings"),
                    Horizontal(
                        Button("🔍 Dry-run", id="dry-run-btn", variant="primary"),
                        Button("🚀 Apply", id="apply-btn", variant="error"),
                        id="pol-actions",
                    ),
                    DataTable(id="pol-table"),
                    RichLog(id="pol-log", highlight=True, markup=True, max_lines=200),
                    id="pol-detail",
                ),
                id="pol-main",
            ),
        )
        yield Static("Press [bold]R[/bold] to scan all services", id="pol-summary")

    def on_mount(self):
        self.call_later(self.action_refresh)

    def action_refresh(self):
        log = self.query_one("#pol-log", RichLog)
        log.clear()

        tree = self.query_one("#pol-tree", Tree)
        tree.clear()

        table = self.query_one("#pol-table", DataTable)
        table.clear()

        summary = self.query_one("#pol-summary", Static)
        summary.update("[bold yellow]Scanning all services...[/bold yellow]")

        self._log("[bold yellow]Starting dynamic policy scan...[/bold yellow]")
        asyncio.get_event_loop().run_in_executor(None, self._run_scan)

    def _safe_call(self, fn):
        try:
            self.app.call_from_thread(fn)
        except Exception:
            pass

    def _run_scan(self):
        try:
            session = AwsSession()
            engine = PolicyEngine(session, dry_run=True, on_log=self._on_log)
            policies = engine.scan_all()
            self._safe_call(
                functools.partial(self._on_scan_complete, policies)
            )
        except Exception as e:
            self._safe_call(
                functools.partial(self._log, f"[red]Scan error: {e}[/red]")
            )

    def _on_scan_complete(self, policies):
        self._policies = policies
        tree = self.query_one("#pol-tree", Tree)
        tree.clear()
        tree.root.expand()

        for pol in policies:
            savings_str = f"${pol.estimate_monthly:.2f}/mo" if pol.estimate_monthly else ""
            label = f"{pol.icon} {pol.label} [bold]({pol.count})[/bold] {savings_str}"
            node = tree.root.add(label)
            node.data = pol

        summary = self.query_one("#pol-summary", Static)
        total_savings = sum(p.estimate_monthly for p in policies)
        summary.update(
            f"[bold green]Scan complete:[/bold green] {len(policies)} policies, "
            f"[bold]${total_savings:.2f}/month[/bold] potential savings"
        )

    def on_tree_node_selected(self, event: Tree.NodeSelected):
        node = event.node
        if not node.data:
            return

        pol = node.data
        title = self.query_one("#pol-title", Static)
        savings_w = self.query_one("#pol-savings", Static)
        table = self.query_one("#pol-table", DataTable)

        savings_str = f"${pol.estimate_monthly:.2f}/month" if pol.estimate_monthly else "No direct cost"
        title.update(f"[bold]{pol.icon} {pol.label}[/bold]")
        savings_w.update(f"[green]Estimated savings: {savings_str}[/green]  |  {pol.count} resources")

        table.clear()
        table.add_columns(*pol.cols)
        for c in pol.candidates:
            row = [str(v) for v in list(c.values())[:len(pol.cols)]]
            while len(row) < len(pol.cols):
                row.append("")
            table.add_row(*row)

    def _log(self, msg: str):
        log = self.query_one("#pol-log", RichLog)
        log.write(msg)

    def _on_log(self, msg: str):
        try:
            self.app.call_from_thread(functools.partial(self._log, msg))
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed):
        tree = self.query_one("#pol-tree", Tree)
        selected = tree.cursor_node
        if not selected or not selected.data:
            self._log("[yellow]Select a policy first[/yellow]")
            return

        pol = selected.data
        is_dry_run = event.button.id == "dry-run-btn"

        log = self.query_one("#pol-log", RichLog)
        log.clear()

        summary = self.query_one("#pol-summary", Static)

        if is_dry_run:
            summary.update(f"[bold]Dry-run: {pol.label}...[/bold]")
            self._log(f"[bold yellow]Dry-run: {pol.label}[/bold yellow]")
            self._log(f"[bold]{pol.count}[/bold] resources found")
            self._log(f"[green]Estimated savings: ${pol.estimate_monthly:.2f}/month[/green]")
            table = self.query_one("#pol-table", DataTable)
            table.clear()
            table.add_columns(*pol.cols)
            for c in pol.candidates:
                vals = [str(list(c.values())[i]) if i < len(list(c.values())) else ""
                        for i in range(len(pol.cols))]
                table.add_row(*vals)
            summary.update(f"[bold green]Dry-run complete:[/bold green] {pol.count} resources")
        else:
            self.app.push_screen(
                ConfirmScreen(pol.label, pol.count, f"${pol.estimate_monthly:.2f}/mo"),
                lambda confirmed: self._on_apply_confirmed(pol, confirmed),
            )

    def _on_apply_confirmed(self, pol, confirmed: bool):
        if not confirmed:
            self._log("[yellow]Cancelled[/yellow]")
            return

        log = self.query_one("#pol-log", RichLog)
        log.clear()

        summary = self.query_one("#pol-summary", Static)
        summary.update(f"[bold]Applying {pol.label}...[/bold]")

        self._log(f"[bold red]Applying: {pol.label}[/bold red]")
        asyncio.get_event_loop().run_in_executor(
            None, self._run_apply, pol,
        )

    def _run_apply(self, pol):
        try:
            session = AwsSession()
            engine = PolicyEngine(session, dry_run=False, on_log=self._on_log)
            engine.apply(pol)
            self._safe_call(
                functools.partial(self._log,
                                  f"[bold green]Applied: {pol.label} ({pol.count} resources)[/bold green]")
            )
            self._safe_call(
                functools.partial(self._log_policy_action, pol)
            )
            self._safe_call(
                functools.partial(
                    self.query_one("#pol-summary", Static).update,
                    f"[bold green]Applied: {pol.label} — {pol.count} resources[/bold green]"
                )
            )
        except Exception as e:
            self._safe_call(
                functools.partial(self._log, f"[red]Error: {e}[/red]")
            )

    def _log_policy_action(self, pol):
        from services.history import OptimizationHistory
        session = AwsSession()
        user = session.get_current_user()
        history = OptimizationHistory()
        history.add_entry(
            category=f"policy:{pol.key}",
            resource_id=f"bulk_{pol.count}_items",
            description=f"Applied {pol.label} — ${pol.estimate_monthly:.2f}/mo savings",
            user=user,
            savings=f"${pol.estimate_monthly:.2f}/mo",
        )
