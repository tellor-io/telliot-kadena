from typing import Any

import click
from click.core import Context
from telliot_core.apps.core import TelliotCore
from telliot_core.cli.utils import async_run
from telliot_feeds.datafeed import DataFeed
from telliot_feeds.feeds import CATALOG_FEEDS
from telliot_feeds.queries.query_catalog import query_catalog
from telliot_feeds.utils.log import get_logger

from telliot_kadena.cli.utils import build_spot_from_input
from telliot_kadena.cli.utils import check_endpoint
from telliot_kadena.cli.utils import get_accounts_from_name
from telliot_kadena.cli.utils import print_reporter_settings
from telliot_kadena.cli.utils import setup_config
from telliot_kadena.config.kelliot_config import KelliotConfig
from telliot_kadena.contracts.module import Module
from telliot_kadena.contracts.tellorflex_kadena import TellorFlexKadena
from telliot_kadena.reporters.kadenaReporter import KadenaReporter

""" Telliot CLI

A simple interface for interacting with telliot_feeds's functionality.
Configure telliot_feeds's settings via this interface's command line flags
or in the configuration file.
"""

logger = get_logger(__name__)
logger.setLevel("DEBUG")


def reporter_cli_core(ctx: click.Context) -> TelliotCore:
    """Returns a TelliotCore configured with the CLI context

    The returned object should be used as a context manager for CLI commands
    """
    account_name = ctx.obj.get("ACCOUNT_NAME", None)

    cfg = KelliotConfig()
    if ctx.obj.get("CHAIN_ID", None):
        cfg.main.chain_id = ctx.obj["CHAIN_ID"]
    if ctx.obj.get("NETWORK", None):
        cfg.main.network = ctx.obj["NETWORK"]

    core = TelliotCore(config=cfg, account_name=account_name)
    return core


STAKE_MESSAGE = (
    "\U00002757Telliot will automatically stake more TRB "
    "if your stake is below or falls below the stake amount required to report.\n"
    "If you would like to stake more than required, enter the TOTAL stake amount you wish to be staked.\n"
    "For example, if you wish to stake 1000 TRB, enter 1000.\n"
)


@click.group()
def reporter() -> None:
    """Report data on-chain."""
    pass


@click.option(
    "--account",
    "-a",
    "account_str",
    help="Name of account used for reporting, staking, etc. More info: run `telliot account --help`",
    required=True,
    nargs=1,
    type=str,
)
@click.option(
    "--network",
    "-n",
    "network",
    help="testnet or mainnet",
    required=True,
    nargs=1,
    type=str,
)
@reporter.command()
@click.option(
    "--build-spot",
    "-b",
    "build_spot",
    help="build a datafeed from a query type and query parameters",
    is_flag=True,
)
@click.option(
    "--query-tag",
    "-qt",
    "query_tag",
    help="select datafeed using query tag",
    required=False,
    nargs=1,
    type=click.Choice([q.tag for q in query_catalog.find(query_type="SpotPrice")]),
)
@click.option(
    "--gas-limit",
    "-gl",
    "gas_limit",
    help="use custom gas limit",
    nargs=1,
    type=int,
    default=150000,
)
@click.option(
    "--gas-price",
    "-gp",
    "gas_price",
    default=1.0e-7,
)
@click.option(
    "-wp",
    "--wait-period",
    help="wait period between feed suggestion calls",
    nargs=1,
    type=int,
    default=7,
)
@click.option(
    "--stake",
    "-s",
    "stake",
    help=STAKE_MESSAGE,
    nargs=1,
    type=float,
    default=10.0,
)
@click.option(
    "--min-native-token-balance",
    "-mnb",
    "min_native_token_balance",
    help="Minimum native token balance required to report. Denominated in ether.",
    nargs=1,
    type=float,
    default=0.25,
)
@click.option("--submit-once/--submit-continuous", default=False)
@click.option("-pwd", "--password", type=str)
@click.pass_context
@async_run
async def report(
    ctx: Context,
    query_tag: str,
    build_spot: bool,
    gas_limit: int,
    gas_price: float,
    submit_once: bool,
    wait_period: int,
    password: str,
    min_native_token_balance: float,
    stake: float,
    account_str: str,
    network: str,
) -> None:
    """Report values to Tellor oracle"""
    ctx.obj["ACCOUNT_NAME"] = account_str
    ctx.obj["NETWORK"] = network

    accounts = get_accounts_from_name(account_str)
    if not accounts:
        return
    print(f"Using keyset: {accounts[0].address}")
    ctx.obj["CHAIN_ID"] = accounts[0].chains[0]  # used in reporter_cli_core

    # Initialize telliot core app using CLI context
    async with reporter_cli_core(ctx) as core:
        core._config, account = setup_config(core.config, account_name=account_str)

        endpoint = check_endpoint(core._config)

        if not endpoint or not account:
            click.echo("Accounts and/or endpoint unset.")
            click.echo(f"Account: {account}")
            click.echo(f"Endpoint: {core._config.get_endpoint()}")
            return

        # Make sure current account is unlocked
        if not account.is_unlocked:
            account.unlock(password)

        # If we need to build a datafeed
        if build_spot:
            chosen_feed = build_spot_from_input()

            if chosen_feed is None:
                click.echo("Unable to build Datafeed from provided input")
                return
        # Use selected feed, or choose automatically
        elif query_tag is not None:
            try:
                chosen_feed: DataFeed[Any] = CATALOG_FEEDS[query_tag]  # type: ignore
            except KeyError:
                click.echo(f"No corresponding datafeed found for query tag: {query_tag}\n")
                return
        else:
            chosen_feed = None

        print_reporter_settings(
            query_tag=query_tag,
            gas_limit=gas_limit,
            gas_price=gas_price,
            chain_id=core.config.main.chain_id,
            stake_amount=stake,
            min_native_token_balance=min_native_token_balance,
        )

        oracle = TellorFlexKadena(account=account, endpoint=endpoint, gas_limit=gas_limit, gas_price=gas_price)
        token = Module(module_name="f-TRB", endpoint=endpoint)
        reporter = KadenaReporter(
            oracle=oracle,
            token=token,
            datafeed=chosen_feed,
            account=account,
            stake=stake,
            endpoint=endpoint,
            wait_period=wait_period,
            gas_limit=gas_limit,
            gas_price=gas_price,
            min_native_token_balance=min_native_token_balance,
        )

        if submit_once:
            _, _ = await reporter.report_once()
        else:
            await reporter.report()
