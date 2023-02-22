from dataclasses import dataclass
from typing import Any
from typing import Dict
from typing import Optional
from typing import Tuple
from typing import Union

from telliot_core.utils.response import error_status
from telliot_core.utils.response import ResponseStatus
from telliot_feeds.utils.log import get_logger

from telliot_kadena.chained.chained_keyset import ChainedAccount
from telliot_kadena.contracts.module import Module
from telliot_kadena.model.chainweb_endpoints import ChainwebEndpoint
from telliot_kadena.utils.exec_cmd import mk_meta
from telliot_kadena.utils.exec_cmd import simple_exec_cmd


logger = get_logger(__name__)


@dataclass
class StakerInfo:
    """Staker Info Dataclass"""

    start_date: int = 0
    stake_balance: int = 0
    locked_balance: int = 0
    reward_debt: int = 0
    last_report: int = 0
    reports_count: int = 0
    start_vote_count: int = 0
    start_vote_tally: int = 0
    is_staked: bool = False


class TellorFlexKadena(Module):
    """TellorFlex Kadena Module Class"""

    def __init__(
        self,
        account: ChainedAccount,
        gas_price: float,
        gas_limit: int,
        endpoint: ChainwebEndpoint,
    ):
        super().__init__(endpoint=endpoint, module_name="tellorflex")
        self.account = account
        self.gas_price = gas_price
        self.gas_limit = gas_limit

    def build_meta(self) -> Dict[str, Union[str, int, float]]:
        """Builds the meta data for the transaction"""
        return mk_meta(
            sender=self.account.name, gas_price=self.gas_price, gas_limit=self.gas_limit, chain_id=self.chain_id
        )

    def deposit_stake(self, amount: int) -> Tuple[Optional[str], ResponseStatus]:
        """Deposits stake for the given amount"""
        function_code = (
            "("
            + self.namespace
            + '.tellorflex.deposit-stake (read-msg "reporter") (read-keyset "keyset") (read-integer "amount"))'
        )
        # comes out reserved first param last in dict
        reporter = self.account.name
        guard = {"pred": self.account.local_account.pred, "keys": self.account.local_account.public_keys}
        data = {"amount": amount, "keyset": guard, "reporter": reporter}
        key_pairs = self.account.local_account.signature()
        caps = [
            {"args": [reporter, "tellorflex", amount / 1e18], "name": self.namespace + ".f-TRB.TRANSFER"},
            {"args": [], "name": "coin.GAS"},
            {"args": [reporter], "name": self.namespace + ".tellorflex.STAKER"},
        ]
        # add caps to last keypair
        key_pairs[-1]["clist"] = caps
        cmd = simple_exec_cmd(
            pact_code=function_code,
            key_pairs=key_pairs,
            env_data=data,
            meta=self.build_meta(),
            network_id=self.network_id,
        )
        request_keys, status = self.request(cmd, "send")
        if not status.ok or request_keys is None:
            return None, error_status(note="Error sending deposit-stake", log=logger.error)

        receipt, status = self.fetch_receipt_with_retry(request_keys.json())
        if not status.ok:
            return None, error_status(note=f"{status.error}: for deposit-stake txn", log=logger.error)
        if receipt == "failure":
            return None, error_status(note="deposit txn failed", log=logger.error)
        return receipt, status

    def submit_value(
        self, query_id: str, value: str, nonce: int, query_data: str
    ) -> Tuple[Optional[str], ResponseStatus]:
        """Submits a value to the TellorFlex contract"""
        function_code = (
            "("
            + self.namespace
            + '.tellorflex.submit-value (read-string "queryId") (read-string "value") (read-integer "nonce") '
            + '(read-string "queryData") (read-string "staker"))'
        )
        staker = self.account.name
        data = {"queryId": query_id, "value": value, "nonce": nonce, "queryData": query_data, "staker": staker}
        cmd = simple_exec_cmd(
            pact_code=function_code,
            key_pairs=self.account.local_account.signature(),
            env_data=data,
            meta=self.build_meta(),
            network_id=self.network_id,
        )
        request_keys, status = self.request(cmd, "send")
        if not status.ok or request_keys is None:
            return None, error_status(note=f"Error sending submit-value: {status.error}", log=logger.error)

        receipt, status = self.fetch_receipt_with_retry(request_keys.json())
        if not status.ok:
            return None, error_status(note=f"{status.error}: for submit-value txn", log=logger.error)
        if receipt == "failure":
            return None, error_status(note="submit-value txn failed", log=logger.error)
        return receipt, status

    def get_staker_info(self, staker: str) -> Tuple[Optional[StakerInfo], ResponseStatus]:
        """Gets the staker info for the given staker"""
        api_response, status = self.read(function_name="get-staker-info", staker=staker)
        if not status.ok:
            if status.error == f"read: row not found: {staker}":
                # if reporter is not staked the api returns an error
                # with message "read: row not found: <account>"
                return parse_staker_info(), ResponseStatus()
            return None, error_status(note="Error getting staker info", e=status.error, log=logger.warning)
        return parse_staker_info(api_response), ResponseStatus()

    def get_new_value_count_by_query_id(self, query_id: str) -> Tuple[Optional[int], ResponseStatus]:
        """Gets the new value count for the given query id"""
        api_response, status = self.read(function_name="get-new-value-count-by-query-id", queryId=query_id)
        if not status.ok:
            if status.error == f"read: row not found: {query_id}":
                return 0, ResponseStatus()
            return None, error_status(note="Error reading new value count", e=status.error, log=logger.warning)
        return api_response, ResponseStatus()

    def stake_amount(self) -> Tuple[Optional[Dict[str, str]], ResponseStatus]:
        """Gets the stake amount"""
        api_response, status = self.read(function_name="stake-amount")
        if not status.ok:
            return None, error_status(note=status.error, log=logger.error)
        return api_response, ResponseStatus()


def parse_staker_info(response: Optional[Dict[str, Any]] = None) -> StakerInfo:
    """Parses the staker info from the api response"""
    if response is None:
        return StakerInfo()
    return StakerInfo(
        start_date=response["start-date"]["int"],
        stake_balance=int(response["staked-balance"]["int"]),
        locked_balance=int(response["locked-balance"]["int"]),
        reward_debt=response["reward-debt"]["int"],
        last_report=response["reporter-last-timestamp"]["int"],
        reports_count=response["reports-submitted"]["int"],
        start_vote_count=response["start-vote-count"]["int"],
        start_vote_tally=response["start-vote-tally"]["int"],
        is_staked=response["is-staked"],
    )
