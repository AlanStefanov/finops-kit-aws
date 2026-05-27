from textual.app import ComposeResult
from textual.widgets import Static, DataTable
from textual.containers import Container

from services.history import OptimizationHistory


class HistoryPanel(Container):
    CSS = """
    HistoryPanel {
        background: $surface;
    }

    .header-box {
        height: 3;
        content-align: center middle;
        background: $accent;
        color: $text;
        text-style: bold;
    }

    #history-summary {
        height: 3;
        margin: 1;
        padding: 1;
        border: solid $primary;
        content-align: center middle;
    }

    #history-table {
        height: 1fr;
        margin: 1;
    }
    """

    def compose(self):
        yield Static("Optimization History Log", classes="header-box")
        yield Static(id="history-summary")
        yield DataTable(id="history-table")

    def on_mount(self):
        self.call_later(self._load_history)

    def _load_history(self):
        try:
            history = OptimizationHistory()
            records = history.get_all()
            summary = history.get_summary()

            summary_w = self.query_one("#history-summary", Static)
            summary_w.update(
                f"[bold]Total actions: {summary['total']}[/bold] | "
                f"Users: {', '.join(f'{u}({c})' for u, c in summary['by_user'].items())}"
            )

            table = self.query_one("#history-table", DataTable)
            table.clear()
            table.add_columns("Date/Time", "Category", "Resource", "Description", "User", "Savings")
            table.zebra_stripes = True

            for r in records:
                table.add_row(
                    r.get("timestamp", ""),
                    r.get("category", ""),
                    r.get("resource_id", ""),
                    r.get("description", ""),
                    r.get("user", ""),
                    r.get("savings", ""),
                )

        except Exception as e:
            summary_w = self.query_one("#history-summary", Static)
            summary_w.update(f"[red]Error loading history: {e}[/red]")
