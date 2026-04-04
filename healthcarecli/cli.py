"""Root CLI entry point."""

from typing import Optional

import typer
from rich.console import Console
from rich.text import Text

from healthcarecli.dataset import cli as dataset_cli
from healthcarecli.dicom import cli as dicom_cli
from healthcarecli.fhir import cli as fhir_cli

VERSION = "0.1.0"

BANNER = r"""
 ╦ ╦╔═╗╔═╗╦  ╔╦╗╦ ╦╔═╗╔═╗╦═╗╔═╗  ╔═╗╦  ╦
 ╠═╣║╣ ╠═╣║   ║ ╠═╣║  ╠═╣╠╦╝║╣   ║  ║  ║
 ╩ ╩╚═╝╩ ╩╩═╝╩ ╩ ╩╚═╝╩ ╩╩╚═╚═╝  ╚═╝╩═╝╩
"""


def _print_banner() -> None:
    console = Console()
    banner_text = Text(BANNER, style="bold cyan")
    console.print(banner_text, highlight=False)
    console.print(f"  v{VERSION}\n", style="green")


app = typer.Typer(
    name="healthcarecli",
    help="Cross-platform CLI for healthcare interoperability — DICOM, FHIR, HL7.",
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", help="Show version and exit.", is_eager=True
    ),
) -> None:
    """Cross-platform CLI for healthcare interoperability — DICOM, FHIR, HL7."""
    if version:
        _print_banner()
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        _print_banner()
        console = Console()
        console.print(ctx.get_help())
        raise typer.Exit()


app.add_typer(dataset_cli.app, name="dataset")
app.add_typer(dicom_cli.app, name="dicom")
app.add_typer(fhir_cli.app, name="fhir")


@app.command("init")
def init() -> None:
    """Guided setup wizard — configure your first PACS/FHIR/HL7 connection."""
    from healthcarecli.init_cmd import run_init

    run_init()
