from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, TabbedContent, TabPane
from textual.binding import Binding

from screens.splash import SplashScreen
from screens.dashboard import DashboardPanel
from screens.optimization import OptimizationPanel
from screens.history import HistoryPanel
from screens.policies import PoliciesPanel
from screens.backup import BackupPanel


class FinOpsKit(App):
    CSS = """
    Screen {
        background: $surface;
    }

    TabbedContent {
        height: 1fr;
    }
    """

    TITLE = "FinOpsKit for AWS"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "switch_tab('dashboard')", "Dashboard"),
        Binding("o", "switch_tab('optimization')", "Optimization"),
        Binding("p", "switch_tab('policies')", "Policies"),
        Binding("h", "switch_tab('history')", "History"),
        Binding("b", "switch_tab('backup')", "Backup"),
        Binding("r", "refresh", "Refresh"),
    ]

    def compose(self):
        yield Header(show_clock=True)
        with TabbedContent(initial="dashboard"):
            with TabPane("📊 Dashboard", id="dashboard"):
                yield DashboardPanel()
            with TabPane("🧹 Optimization", id="optimization"):
                yield OptimizationPanel()
            with TabPane("📜 History", id="history"):
                yield HistoryPanel()
            with TabPane("⚙️ Policies", id="policies"):
                yield PoliciesPanel()
            with TabPane("💾 Backup", id="backup"):
                yield BackupPanel()
        yield Footer()

    def on_mount(self):
        self.push_screen(SplashScreen())

    def action_switch_tab(self, tab: str):
        tabs = self.query_one(TabbedContent)
        tabs.active = tab

    def action_refresh(self):
        tabs = self.query_one(TabbedContent)
        active = tabs.active
        if active == "dashboard":
            panel = self.query_one(DashboardPanel)
            panel._load_data()
        elif active == "optimization":
            panel = self.query_one(OptimizationPanel)
            panel.refresh_data()
        elif active == "history":
            panel = self.query_one(HistoryPanel)
            panel._load_history()
        elif active == "policies":
            panel = self.query_one(PoliciesPanel)
            panel.action_refresh()
        elif active == "backup":
            panel = self.query_one(BackupPanel)
            panel.action_refresh_instances()


if __name__ == "__main__":
    app = FinOpsKit()
    app.run()
