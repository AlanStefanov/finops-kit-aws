from textual.app import ComposeResult
from textual.widgets import DataTable, Static
from textual.containers import Container

from services.aws_session import AwsSession
from services.cost_explorer import CostExplorerService


class DashboardPanel(Container):
    CSS = """
    DashboardPanel {
        background: $surface;
    }

    .header-box {
        height: 3;
        content-align: center middle;
        background: $primary;
        color: $text;
        text-style: bold;
    }

    #totals-panel {
        height: 5;
        margin: 1;
        padding: 1;
        border: solid $primary;
    }

    #service-table {
        height: 1fr;
        margin: 1;
    }
    """

    def compose(self):
        yield Static("AWS Cost Explorer - Dashboard", classes="header-box")
        yield Container(id="totals-panel")
        yield DataTable(id="service-table")

    def on_mount(self):
        self.set_timer(5.5, self._load_data)

    def _load_data(self):
        totals_panel = self.query_one("#totals-panel", Container)
        totals_panel.remove_children()
        totals_panel.mount(Static("Fetching cost data from AWS...", id="loading"))

        try:
            session = AwsSession()
            ce = CostExplorerService(session)

            totals = ce.get_total_cost(months=3)
            services = ce.get_monthly_cost_by_service(months=3)

            totals_panel.remove_children()
            for period, amount in sorted(totals.items()):
                month_label = period[-2:]
                totals_panel.mount(
                    Static(f"[bold]Month {month_label}[/bold]\n${amount:,.2f}")
                )

            table = self.query_one("#service-table", DataTable)
            table.clear()

            months = sorted(set(p for svc in services.values() for p in svc))
            columns = ["Service"] + months + ["Total"]
            table.add_columns(*columns)
            table.zebra_stripes = True

            services_sorted = sorted(
                services.items(),
                key=lambda x: sum(x[1].values()),
                reverse=True,
            )

            for service, periods in services_sorted:
                row = [service]
                svc_total = 0
                for m in months:
                    val = periods.get(m, 0)
                    row.append(f"${val:,.2f}")
                    svc_total += val
                row.append(f"${svc_total:,.2f}")
                table.add_row(*row)

        except Exception as e:
            totals_panel = self.query_one("#totals-panel", Container)
            totals_panel.remove_children()
            totals_panel.mount(
                Static(f"[red]Error: {e}[/red]\nCheck your AWS credentials and permissions.")
            )
