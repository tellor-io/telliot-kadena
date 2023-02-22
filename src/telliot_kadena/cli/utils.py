from typing import List
from typing import Optional
from typing import Tuple

import click
from simple_term_menu import TerminalMenu
from telliot_feeds.feeds import DataFeed
from telliot_feeds.feeds import DATAFEED_BUILDER_MAPPING
from telliot_feeds.utils.log import get_logger

from telliot_kadena.chained.chained_keyset import ChainedAccount
from telliot_kadena.chained.chained_keyset import find_accounts
from telliot_kadena.config.kelliot_config import KelliotConfig
from telliot_kadena.model.chainweb_endpoints import ChainwebEndpoint

logger = get_logger(__name__)


def setup_config(cfg: KelliotConfig, account_name: str) -> Tuple[KelliotConfig, Optional[ChainedAccount]]:
    """Setup KelliotConfig via CLI if not already configured

    Inputs:
    - cfg (KelliotConfig) -- current Telliot configuration

    Returns:
    - KelliotConfig -- updated Telliot configuration post-setup
    - ChainedAccount -- account configuration to choose as current account
    """

    if cfg is None:
        cfg = KelliotConfig()

    accounts = check_accounts(cfg, account_name)
    endpoint = check_endpoint(cfg)

    click.echo(f"Your current settings...\nYour chain id: {cfg.main.chain_id}\n")

    if endpoint is not None:
        click.echo(
            f"Your {endpoint.network} endpoint: \n"
            f" - provider: {endpoint.provider}\n"
            f" - RPC url: {endpoint.url}\n"
            f" - explorer url: {endpoint.explorer}"
        )
    else:
        click.echo("No endpoints set.")

    if accounts:
        click.echo(f"Your account: {accounts[0].name} at address {accounts[0].address}")

    else:
        click.echo("No accounts set.")

    keep_settings = click.confirm("Proceed with current settings (y) or update (n)?", default=True)

    if keep_settings:
        click.echo("Keeping current settings...")
        return cfg, accounts[0] if accounts else None

    want_to_update_chain_id = click.confirm(f"Chain_id is {cfg.main.chain_id}. Do you want to update it?")

    if want_to_update_chain_id:  # noqa: F821
        new_chain_id = click.prompt("Enter a new chain id", type=int)
        cfg.main.chain_id = new_chain_id

    new_endpoint = setup_endpoint(cfg, cfg.main.chain_id)
    if new_endpoint is not None:
        cfg.endpoints.endpoints.insert(0, new_endpoint)
        click.echo(f"{new_endpoint} added!")

    click.echo(f"Your account name: {accounts[0].name if accounts else None}")

    new_account = setup_account(cfg.main.chain_id)
    if new_account is not None:
        click.echo(f"{new_account.name} selected!")

    # write new endpoints to file (note: accounts are automatically written to file)
    if cfg._ep_config_file is not None:
        cfg._ep_config_file.save_config(cfg.endpoints)

    return cfg, new_account


def setup_endpoint(cfg: KelliotConfig, chain_id: int) -> Optional[ChainwebEndpoint]:
    """Setup Endpoints via CLI if not already configured"""

    endpoint = check_endpoint(cfg)

    if endpoint is not None:
        keep = click.confirm(f"Do you want to use this endpoint on chain_id {chain_id}?")
        if keep:
            return endpoint
        else:
            return prompt_for_endpoint(chain_id)

    else:
        click.echo(f"No endpoints are available for chain_id {chain_id}. Please add one:")
        return prompt_for_endpoint(chain_id)


def check_endpoint(cfg: KelliotConfig) -> Optional[ChainwebEndpoint]:
    """Check if there is a pre-set endpoint in the config"""

    try:
        return cfg.get_endpoint()
    except Exception as e:
        logger.warning("No endpoints found: " + str(e))
        return None


def check_accounts(cfg: KelliotConfig, account_name: str) -> List[ChainedAccount]:
    """Check if there is a pre-set account in the config"""

    return find_accounts(chain_id=cfg.main.chain_id, name=account_name)


def prompt_for_endpoint(chain_id: int) -> Optional[ChainwebEndpoint]:
    """Take user input to create a new ChainwebEndpoint"""
    rpc_url = click.prompt("Enter RPC URL", type=str)
    explorer_url = click.prompt("Enter block explorer URL", type=str)
    network = click.prompt("Enter network name", type=str)

    try:
        return ChainwebEndpoint(chain_id, network, "n/a", rpc_url, explorer_url)
    except Exception as e:
        click.echo("Cannot add endpoint: invalid endpoint properties" + str(e))
        return None


def setup_account(chain_id: int) -> Optional[ChainedAccount]:
    """Set up ChainedAccount for KelliotConfig if not already configured"""

    accounts = find_accounts(chain_id=chain_id)
    if accounts is None:
        return prompt_for_account(chain_id)

    else:
        title = f"You have these accounts on chain_id {chain_id}"
        options = [[a.name] + a.address for a in accounts] + ["add account..."]

        menu = TerminalMenu(options, title=title)
        selected_index = menu.show()

        if options[selected_index] == "add account...":
            return prompt_for_account(chain_id=chain_id)
        else:
            selected_account = accounts[selected_index]
            click.echo(f"Account {selected_account.name} at {selected_account.address} selected.")
            return selected_account  # type: ignore


def prompt_for_account(chain_id: int) -> Optional[ChainedAccount]:
    """take user input to create a new ChainedAccount account for the Telliot Config"""

    acc_name = click.prompt("Enter account name", type=str)
    private_key = click.prompt("Enter private key/s", type=str)
    chain_id = click.prompt("Enter chain id", type=int)
    predicate = click.prompt("Enter predicate", type=str)

    pks = private_key.split()
    try:
        return ChainedAccount.add_keyset(acc_name, predicate, chain_id, pks, password=None)
    except Exception as e:
        if "already exists" in str(e):
            click.echo(f"Cannot add account: Account {acc_name} already exists :)" + str(e))
        else:
            click.echo("Cannot add account: Invalid account properties" + str(e))
        return None


def print_reporter_settings(
    query_tag: str,
    gas_limit: int,
    chain_id: int,
    gas_price: float,
    stake_amount: float,
    min_native_token_balance: float,
) -> None:
    """Print user settings to console."""
    click.echo("")

    if query_tag:
        click.echo(f"Reporting query tag: {query_tag}")
    else:
        click.echo("Reporting with synchronized queries")

    click.echo(f"Current chain ID: {chain_id}")

    click.echo(f"Gas Limit: {gas_limit}")
    click.echo(f"Gas Price: {gas_price}")
    click.echo(f"Desired stake amount: {stake_amount}")
    click.echo(f"Minimum KDA token balance required to report: {min_native_token_balance}")
    click.echo("\n")

    _ = input("Press [ENTER] to confirm settings.")


def get_accounts_from_name(name: Optional[str]) -> list[ChainedAccount]:
    """Get account from name or return any account if no name is given."""
    accounts: list[ChainedAccount] = find_accounts(name=name) if name else find_accounts()
    if not accounts:
        click.echo(
            f'No keyset found named: "{name}".\nAdd one with the keyset subcommand.'
            "\nFor more info run: `kadena keyset add --help`"
        )
    return accounts


def build_spot_from_input() -> Optional[DataFeed]:
    """Build a SpotPrice feed from user input"""
    click.echo("Building SpotPrice: ")
    feed = DATAFEED_BUILDER_MAPPING["SpotPrice"]

    for query_param in ("asset", "currency"):
        val = click.prompt(f"Enter value for QueryParameter {query_param}")

        if val is not None:
            try:
                val = str(val)
                setattr(feed.query, query_param, val)
                setattr(feed.source, query_param, val)
            except ValueError:
                click.echo(f"Value {val} for QueryParameter {query_param} should be of type str")
                return None
        else:
            click.echo(f"Must set QueryParameter {query_param} of QueryType str")
            return None

    return feed
