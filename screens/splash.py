import asyncio
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static, ProgressBar
from textual.containers import Center, Middle


class SplashScreen(Screen):
    CSS = """
    SplashScreen {
        align: center middle;
        background: $surface;
    }

    #splash-box {
        width: 60;
        height: 15;
        border: double $primary;
        padding: 1 2;
    }

    #splash-title {
        content-align: center middle;
        text-style: bold;
        color: $primary;
        height: 3;
    }

    #splash-subtitle {
        content-align: center middle;
        height: 1;
    }

    #splash-author {
        content-align: center middle;
        color: $text-muted;
        height: 1;
    }

    #splash-loader {
        height: 3;
        margin: 1 4;
    }

    ProgressBar {
        height: 1;
    }

    #splash-status {
        content-align: center middle;
        color: $text-muted;
        height: 1;
    }
    """

    def compose(self):
        yield Center(
            Middle(
                Static("", id="splash-box"),
            ),
        )

    def on_mount(self):
        self.set_timer(0.1, self._render_content)

    def _render_content(self):
        box = self.query_one("#splash-box", Static)
        box.update(
            "[bold]# Bienvenido[/bold]\n\n"
            "[bold]$ FinOpsKit for AWS[/bold]\n\n"
            "Bienvenido al analizador de costo y\n"
            "optimizador para AWS Web Services\n\n"
            "Desarrollado por Alan Stefanov\n\n"
            "[bold]Presione cualquier tecla para continuar[/bold]"
        )

        self.set_timer(5.0, self._dismiss)

    def _dismiss(self):
        try:
            self.app.pop_screen()
        except Exception:
            pass

    def on_key(self, event):
        self._dismiss()

    def on_click(self, event):
        self._dismiss()
