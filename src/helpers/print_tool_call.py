import json
from rich.console import Console
from rich.text import Text
from rich.align import Align
from rich.panel import Panel
from rich.pretty import Pretty

#console = Console()
console = Console(force_terminal=True, color_system="truecolor")

def print_tool_output(func_name: str, params: str, output):
    header = Text()
    header.append("TOOL: ", style="bold bright_cyan")
    header.append(f"{func_name}\n", style="bold bright_yellow")

    header.append("PARAMS: ", style="bold bright_cyan")
    header.append(f"{params}", style="bright_white")

    info_panel = Panel(
        Align.left(header),
        title="RESULTADO",
        title_align="left",
        border_style="bright_magenta",
        padding=(1, 2),
    )

    output_panel = Panel(
        Pretty(output, expand_all=True),
        title="[bold bright_magenta]TOOL OUTPUT[/bold bright_magenta]",
        title_align="left",
        border_style="bright_magenta",
        padding=(1, 2),
    )

    console.print(info_panel)
    console.print(output_panel)
    console.print()

def print_tool_call(func_name: str, params: str):
    body = Text()
    body.append("Função: ", style="bold bright_cyan")
    body.append(f"{func_name}\n", style="bold bright_yellow")

    body.append("Params: ", style="bold bright_cyan")
    body.append(params, style="bright_white")

    panel = Panel(
        Align.left(body),
        title="🔍 TOOL CALL",
        title_align="left",
        border_style="bright_blue",
        padding=(1, 2),
    )

    console.print(panel)