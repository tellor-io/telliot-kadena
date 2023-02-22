import click
from click.core import Context
from telliot_feeds.utils.log import get_logger

from telliot_kadena import __version__
from telliot_kadena.cli.commands.config import config
from telliot_kadena.cli.commands.keyset import keyset
from telliot_kadena.cli.commands.report import report

""" Telliot CLI

A simple interface for interacting with telliot_feeds's functionality.
Configure telliot_feeds's settings via this interface's command line flags
or in the configuration file.
"""

logger = get_logger(__name__)


@click.group(invoke_without_command=True)
@click.option("--version", is_flag=True, help="Display package version and exit.")
@click.pass_context
def main(
    ctx: Context,
    version: bool,
) -> None:
    """Telliot command line interface"""
    ctx.ensure_object(dict)
    if version:
        print(f"Version: {__version__}")
        return


main.add_command(config)
main.add_command(keyset)
main.add_command(report)
