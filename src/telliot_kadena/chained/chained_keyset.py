# This module was adapted from the chained_accounts package by pyDefi
# https://github.com/pydefi/chained-accounts
"""Chained account/key management

This module is intended to provide a higher degree of security than storing private keys in clear text.
Use at your own risk.
"""
from __future__ import annotations

import getpass
import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from telliot_kadena.chained.exceptions import AccountLockedError
from telliot_kadena.chained.exceptions import ConfirmPasswordError
from telliot_kadena.chained.keyfile import decrypt
from telliot_kadena.chained.keyfile import encrypt
from telliot_kadena.chained.keyfile import restore_pub_key


def default_homedir() -> Path:
    """Returns the default home directory used for the keystore.

    If the directory does not exist, it will be created.

    Returns:
        pathlib.Path : Path to home directory
    """
    homedir = Path.home() / (".chained_accounts")
    homedir = homedir.resolve().absolute()
    if not homedir.is_dir():
        homedir.mkdir()

    return homedir


CHAINED_ACCOUNTS_HOME = default_homedir()

if not CHAINED_ACCOUNTS_HOME.exists():
    CHAINED_ACCOUNTS_HOME.mkdir()


def ask_for_password(name: str) -> str:
    password1 = getpass.getpass(f"Enter encryption password for {name}: ")
    password2 = getpass.getpass("Confirm password: ")
    if password2 != password1:
        raise ConfirmPasswordError(f"Account: {name}")
    password = password1

    return password


class LocalKeyset:
    def __init__(self, account: ChainedAccount, key: List[str], pred: str):
        # Initialize the instance variables
        self.account = account  # the account associated with the keyset
        self.key = key  # a list of secret keys
        self.pred = pred  # the predicate associated with the keyset

        # Restore the public keys from the secret keys
        self.public_keys = [restore_pub_key(k) for k in self.key]

    # Generate a list of dictionary containing public and secret keys for each key in the keyset
    def signature(self) -> List[Dict[str, Any]]:
        return [{"public_key": k, "secret_key": p} for k, p in zip(self.public_keys, self.key)]

    # Return the predicate associated with the keyset
    def predicate(self) -> str:
        return self.pred


class ChainedAccount:
    """Chained Account

    The ChainedAccount class provides access to a keystore for kadena keyset, where each keyset is
    associated with one or more chains.

    ChainedAccount objects default to a locked state, with the private key remaining encrypted.
    The `decrypt()` method must be called prior to accessing the key attribute, otherwise an exception
    will be raised.

    Attributes:
        name:
            User-specified account name (no spaces and should coin account name).
        chains:
            List of applicable chain IDs for this account.
        is_unlocked:
            Returns true if the account is unlocked (key is exposed!).
        key:
            Returns the private key if the account is unlocked, otherwise an exception is raised.
        keyfile:
            Returns the path to the stored keyfile
    """

    _chains: List[int]
    _account_json: Dict[str, Any]

    def __init__(self, name: str):
        """Get an account from the keystore

        Accounts must first be added to the keystore using `ChainedAccount.add()`

        Args:
            name: Unique account name
        """

        self.name: str = name
        self._local_account: Optional[LocalKeyset] = None
        self._chains = []
        try:
            self._load()
        except FileNotFoundError:
            self._account_json = {}

    def __repr__(self) -> str:
        return f"ChainedKeyset('{self.name}')"

    @classmethod
    def get(cls, name: str) -> ChainedAccount:
        """Get an account from the keystore"""
        return cls(name)

    @classmethod
    def add_keyset(
        cls,
        name: str,
        pred: str,
        chains: Union[int, List[int]],
        keys: List[str],
        password: Optional[str] = None,
    ) -> ChainedAccount:
        """Add a new ChainedAccount keyset to the keystore.

        Args:
            name:
                Account name
            chains:
                List of applicable Kadena chain IDs for this account.
            key:
                List of Private Keys for the keyset account.  User will be prompted for password if not provided.
            password:
                Password used to encrypt the keystore

        Returns:
            A new ChainedAccount
        """

        names = list_names()
        if name in names:
            raise Exception(f"Account {name} already exists ")

        self = cls(name=name)

        if isinstance(chains, int):
            chains = [chains]

        self._chains = chains

        if password is None:
            try:
                password = ask_for_password(name)
            except ConfirmPasswordError:
                print("Passwords do not match. Try again.")
                password = ask_for_password(name)

        if password is None:
            password1 = getpass.getpass(f"Enter encryption password for {name}: ")
            password2 = getpass.getpass("Confirm password: ")
            if password2 != password1:
                raise ConfirmPasswordError(f"Account: {name}")
            password = password1
        keystore_json = encrypt(keys, password)
        self._account_json = {"chains": chains, "pred": pred, "keystore_json": keystore_json}
        self._account_json["address"] = [restore_pub_key(key) for key in keys]
        self._store()

        return self

    def unlock(self, password: Optional[str] = None) -> None:
        """Decrypt keystore data.

        Args:
            password: Used to decrypt the keyfile data
        """
        if self.is_unlocked:
            return

        if password is None:
            password = getpass.getpass(f"Enter password for {self.name} account: ")

        keys = decrypt(self._account_json["keystore_json"], password)
        self._local_account = LocalKeyset(self, keys, self._account_json["pred"])

    def lock(self) -> None:
        """Lock account"""
        self._local_account = None

    @property
    def chains(self) -> List[int]:
        """List of applicable chain IDs for this account"""
        if not self._chains:
            self._chains = self._account_json["chains"]

        return self._chains

    @property
    def is_unlocked(self) -> bool:
        """Check if account is unlocked"""
        return self._local_account is not None

    @property
    def key(self) -> List[str]:
        if self.is_unlocked:
            assert self._local_account is not None
            return [key for key in self._local_account.key]
        else:
            raise AccountLockedError(f"{self.name} ChainedAccount must be unlocked to access the private key.")

    @property
    def address(self) -> List[str]:
        return list(self._account_json["address"])

    @property
    def local_account(self) -> LocalKeyset:
        if self.is_unlocked:
            assert self._local_account is not None
            return self._local_account
        else:
            raise AccountLockedError(f"{self.name} LocalKeyset cannot be accessed when ChainedAccount is locked.")

    # --------------------------------------------------------------------------------
    # File access methods
    # --------------------------------------------------------------------------------
    @property
    def keyfile(self) -> Path:
        """Returns the path to the locally stored keyfile"""
        return CHAINED_ACCOUNTS_HOME / f"{self.name}.json"

    def _load(self) -> None:
        """Load the account from disk."""
        if not self.keyfile.exists():
            raise FileNotFoundError(f"Could not load keyfile: {self.keyfile}")

        with open(self.keyfile, "r") as f:
            self._account_json = json.load(f)

    def _store(self) -> None:
        """Store the encrypted account to disk."""
        if self.keyfile.exists():
            raise FileExistsError(f"Keyfile already exists: {self.keyfile}")

        with open(self.keyfile, "w") as f:
            json.dump(self._account_json, f, indent=2)

    def delete(self) -> None:
        if self.keyfile.exists():
            self.keyfile.unlink()


def list_names() -> List[str]:
    """Get a list of all account names"""
    names = [f.stem for f in CHAINED_ACCOUNTS_HOME.iterdir()]

    return names


def find_accounts(
    name: Optional[str] = None,
    chain_id: Optional[int] = None,
    address: Optional[List[str]] = None,
) -> List[ChainedAccount]:
    """Search for matching accounts.

    If no arguments are provided, all accounts will be returned.

    Args:
        name: search by account name
        chain_id: search for accounts with matching chain_id
        address: search for accounts with matching address

    Returns:
        List of matching accounts
    """

    accounts = []
    for acc_name in list_names():
        account = ChainedAccount(acc_name)
        if name is not None:
            if name != account.name:
                continue
        if chain_id is not None:
            if chain_id not in account.chains:
                continue
        if address is not None:
            if address != account.address:
                continue

        accounts.append(account)

    return accounts
