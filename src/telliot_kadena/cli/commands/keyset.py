import getpass
from typing import List

import click

from telliot_kadena.chained.chained_keyset import ChainedAccount
from telliot_kadena.chained.chained_keyset import find_accounts


@click.group()
def keyset() -> None:
    """Add keysets to the keystore"""
    pass


@keyset.command()
@click.argument("name", type=str)
@click.argument("keys", type=str, nargs=1)
@click.argument("pred", type=str)
@click.argument("chains", type=int, nargs=-1)
def add(name: str, keys: str, pred: str, chains: List[int]) -> None:
    """Add a keyset to the keystore.

    Adds a chainweb keyset  for use by an application on one or more Chainweb chains.
    NAME is used to uniquely identify the keyset in the keystore.
    The private KEY should be provided in hexadecimal format.
    CHAIN_IDS is a list of the chains on which applications may use this account.
    """

    test_account = ChainedAccount(name)
    if test_account.keyfile.exists():
        click.echo(f"Account {name} already exists.")
        return
    keys_list = keys.split()
    account = ChainedAccount.add_keyset(name, pred=pred, keys=keys_list, chains=chains)

    click.echo(f"Added new account {name} (address= {account.address}) for use on chains {account.chains}")


@keyset.command()
@click.option("--name", type=str)
@click.option("--address", type=str)
@click.option("--chain_id", type=int)
def find(name: str, address: str, chain_id: int) -> None:
    """Search the keystore for accounts.

    Each option is used as a filter when searching the keystore.
    If no options are provided, all accounts will be returned.
    """
    addresses = address.split() if address is not None else address
    accounts = find_accounts(name=name, address=addresses, chain_id=chain_id)
    click.echo(f"Found {len(accounts)} accounts.")
    for account in accounts:
        click.echo(f"Account name: {account.name}, address: {account.address}, chain IDs: {account.chains}")


@keyset.command()
@click.argument("name", type=str)
@click.option("-p", "--password", type=str)
def key(name: str, password: str) -> None:
    """Get the private key for an account.

    NAME is the account name used to create the account.
    User will be prompted for the password if it is not provided through the command line option.
    """

    account = ChainedAccount(name)
    if not account.keyfile.exists():
        click.echo(f"Account {name} does not exist.")
        return

    try:
        if not password:
            password = getpass.getpass(f"Enter password for {name} keyfile: ")
        acc = ChainedAccount(name)
        acc.unlock(password)
        if isinstance(acc.key, list):
            click.echo(f"Private keys: {[k for k in acc.key]}")
        else:
            click.echo(f"Private key: {acc.key.hex()}")
    except ValueError:
        click.echo("Invalid Password")


@keyset.command()
@click.argument("name", type=str)
def delete(name: str) -> None:
    """Delete an account from the keystore.

    NAME is the account name used to create the account.
    """
    account = ChainedAccount(name)
    if not account.keyfile.exists():
        click.echo(f"Account {name} does not exist.")
        return

    account.delete()
