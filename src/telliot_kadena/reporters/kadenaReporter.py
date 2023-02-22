import asyncio
import json
import math
import time
from datetime import timedelta
from typing import Any
from typing import Optional
from typing import Tuple
from typing import Union

from chained_accounts import ChainedAccount
from telliot_core.utils.response import error_status
from telliot_core.utils.response import ResponseStatus
from telliot_feeds.datafeed import DataFeed
from telliot_feeds.utils.log import get_logger
from telliot_feeds.utils.reporter_utils import is_online
from telliot_feeds.utils.reporter_utils import suggest_random_feed

from telliot_kadena.contracts.module import Module
from telliot_kadena.contracts.tellorflex_kadena import StakerInfo
from telliot_kadena.contracts.tellorflex_kadena import TellorFlexKadena
from telliot_kadena.model.chainweb_endpoints import ChainwebEndpoint
from telliot_kadena.utils.encoding import hash
from telliot_kadena.utils.encoding import urlsafe_base64_encode_string

logger = get_logger(__name__)


class KadenaReporter:
    """Reports values from given datafeeds to the TellorFlex contract
    every 7 seconds."""

    def __init__(
        self,
        account: ChainedAccount,
        endpoint: ChainwebEndpoint,
        oracle: TellorFlexKadena,
        token: Module,
        gas_limit: int,
        gas_price: float,
        wait_period: int = 10,
        datafeed: Optional[DataFeed[Any]] = None,
        min_native_token_balance: float = 10**18,
        stake: float = 0,
    ) -> None:

        self.account = account
        self.node_url = endpoint.url
        self.network = endpoint.network
        self.datafeed = datafeed
        self.acct_name = account.name
        self.gas_limit = gas_limit
        self.gas_price = gas_price
        self.wait_period = wait_period
        self.min_native_token_balance = min_native_token_balance
        self.staker_info: Union[StakerInfo, None] = None
        self.stake: float = stake
        self.stake_amount: Optional[int] = None
        self.oracle = oracle
        self.token = token
        self.random_feed = True if self.datafeed is None else False
        logger.info(f"Reporting with account: {self.acct_name}")

    async def deposit_stake(self, stake: int = 0) -> Tuple[bool, ResponseStatus]:
        # check TRB wallet balance!
        get_wallet_balance, wallet_balance_status = self.token.read(function_name="get-balance", account=self.acct_name)
        if not wallet_balance_status.ok or get_wallet_balance is None:
            return False, error_status(wallet_balance_status.error, log=logger.info)
        # parse balance from response
        wallet_balance = float(get_wallet_balance["decimal"])
        logger.info(f"Current wallet TRB balance: {wallet_balance}")
        # check if wallet balance is enough to cover stake
        if stake / 1e18 > wallet_balance:
            msg = "Not enough TRB in the account to cover the stake"
            return False, error_status(msg, log=logger.warning)
        # deposit stake
        _, deposit_status = self.oracle.deposit_stake(amount=stake)
        if not deposit_status.ok:
            msg = (
                "Unable to stake deposit: "
                + deposit_status.error
                + f"Make sure {self.acct_name} has enough of the current chain's "
                + "currency and the oracle's currency (TRB)"
            )
            return False, error_status(msg, log=logger.error)

        return True, ResponseStatus()

    async def ensure_staked(self) -> Tuple[bool, ResponseStatus]:
        """Ensure that the reporter is staked."""
        # Get oracle current stake amount
        stake_amount, status = self.oracle.stake_amount()
        if not status.ok or stake_amount is None:
            msg = f"Unable to read current stake amount: {status.error}"
            return False, error_status(msg, log=logger.warning)

        # parse stake amount from response
        stake_amount_int = int(stake_amount["decimal"])
        logger.info(f"Current Oracle stakeAmount: {stake_amount_int / 1e18!r}")

        # Get reporter staker info
        stake_info, status = self.oracle.get_staker_info(self.acct_name)
        if not status.ok or stake_info is None:
            msg = f"Unable to read reporters staker info: {status.error}"
            return False, error_status(msg, log=logger.warning)
        # set staker info on first loop
        if self.staker_info is None:
            self.staker_info = stake_info

        # on subsequent loops keeps checking if staked balance in oracle contract decreased
        # if it decreased account is probably in dispute barring withdrawal
        if self.staker_info.stake_balance > stake_info.stake_balance:
            # update balance
            self.staker_info.stake_balance = stake_info.stake_balance
            logger.info("your staked balance has decreased and account might be in dispute")
        # if staked balance is 0 and account is not staked deposit stake
        if not stake_info.is_staked:
            _, status = await self.deposit_stake(stake=stake_amount_int)
            if not status.ok:
                msg = f"Unable to deposit initial stake: {status.error}"
                return False, error_status(msg, log=logger.warning)

            self.staker_info.stake_balance += stake_amount_int
            self.staker_info.is_staked = True
            logger.info("Successfully deposited initial stake")

        # on subsequent loops keeps checking if staked balance in oracle contract decreased
        # if it decreased account is probably in dispute barring withdrawal
        if self.staker_info.stake_balance > stake_info.stake_balance:
            # update balance in script
            self.staker_info.stake_balance = stake_info.stake_balance
            logger.info("your staked balance has decreased and account might be in dispute")

        # after the first loop keep track of the last report's timestamp to calculate reporter lock
        self.staker_info.last_report = stake_info.last_report
        self.staker_info.reports_count = stake_info.reports_count

        logger.info(
            f"""
            STAKER INFO
            start date: {stake_info.start_date}
            staked_balance: {stake_info.stake_balance / 1e18!r}
            locked_balance: {stake_info.locked_balance}
            last report: {stake_info.last_report}
            reports count: {stake_info.reports_count}
            """
        )

        account_staked_bal = self.staker_info.stake_balance

        # after the first loop, logs if stakeAmount has increased or decreased
        if self.stake_amount is not None:
            if self.stake_amount < stake_amount_int:
                logger.info("Stake amount has increased possibly due to TRB price change.")
            elif self.stake_amount > stake_amount_int:
                logger.info("Stake amount has decreased possibly due to TRB price change.")

        self.stake_amount = stake_amount_int

        # deposit stake if stakeAmount in oracle is greater than account stake or
        # a stake in cli is selected thats greater than account stake
        if self.stake_amount > account_staked_bal or (self.stake * 1e18) > account_staked_bal:
            logger.info("Depositing stake...")

            # amount to deposit whichever largest difference either chosen stake or stakeAmount to keep reporting
            stake_diff = max(int(self.stake_amount - account_staked_bal), int((self.stake * 1e18) - account_staked_bal))

            return await self.deposit_stake(stake_diff)

        return True, ResponseStatus()

    async def check_reporter_lock(self) -> ResponseStatus:
        """Checks reporter lock time to determine when reporting is allowed

        Return:
        - ResponseStatus: yay or nay
        """
        if self.staker_info is None or self.stake_amount is None:
            msg = "Unable to calculate reporter lock remaining time"
            return error_status(msg, log=logger.info)

        # 12hrs in seconds is 43200
        reporter_lock = 43200 / math.floor(self.staker_info.stake_balance / self.stake_amount)
        # Get time remaining in reporter lock for the next allowed report
        time_remaining = round(self.staker_info.last_report + reporter_lock - time.time())
        if time_remaining > 0:
            hr_min_sec = str(timedelta(seconds=time_remaining))
            msg = "Currently in reporter lock. Time left: " + hr_min_sec
            return error_status(msg, log=logger.info)

        return ResponseStatus()

    async def fetch_datafeed(self) -> Optional[DataFeed[Any]]:
        """Fetches random datafeed, SpotPrice only."""
        if self.random_feed:
            logger.info("Fetching random datafeed...")
            self.datafeed = suggest_random_feed()
            while self.datafeed.query.type != "SpotPrice":
                self.datafeed = suggest_random_feed()

        return self.datafeed

    async def is_online(self) -> bool:
        # Check internet connection
        online: bool = await is_online()
        return online

    def has_native_token(self) -> bool:
        # Check KDA token balance for gas
        balance, status = self.token.read_any_module(
            module_name_with_namespace="coin", function_name="get-balance", reporter=self.acct_name
        )
        if not status.ok:
            msg = f"Error fetching native token balance for {status.error}"
            logger.warning(msg)
            return False
        expected = self.min_native_token_balance
        if balance < expected:
            msg = f"{self.acct_name} has insufficient native tokens. Balance: {balance}, Expected: {expected}."
            logger.warning(msg)
            return False
        return True

    async def report_once(
        self,
    ) -> Tuple[Optional[str], ResponseStatus]:
        """Report query value once
        This method checks to see if a user is able to submit
        values to the Tellorflex oracle on Kadena, given their staker status
        and last submission time."""

        # Check staker status
        staked, status = await self.ensure_staked()
        if not staked or not status.ok:
            logger.warning(status.error)
            return None, status
        # Check reporter lock
        status = await self.check_reporter_lock()
        if not status.ok:
            return None, status
        # Get suggested datafeed if none provided
        datafeed = await self.fetch_datafeed()
        if not datafeed:
            msg = "Unable to suggest datafeed"
            return None, error_status(note=msg, log=logger.info)

        logger.info(f"Current query: {datafeed.query.descriptor}")

        status = ResponseStatus()

        # Get query info & encode value to bytes
        query = json.loads(datafeed.query.descriptor)
        if query["type"] != "SpotPrice":
            msg = f"Query type {query['type']} not supported"
            return None, error_status(msg, log=logger.info)

        # Update datafeed value
        await datafeed.source.fetch_new_datapoint()
        latest_data = datafeed.source.latest
        if latest_data[0] is None:
            msg = "Unable to retrieve updated datafeed value."
            return None, error_status(msg, log=logger.info)

        # encode query data and query id accoring to tellorflex on kadena
        data_spec = "{{SpotPrice: {{{asset},{currency}}}}}"
        data = data_spec.format(asset=query["asset"], currency=query["currency"])
        query_data = urlsafe_base64_encode_string(data)
        query_id = hash(query_data)

        try:
            value = str(latest_data[0] * 1e18)
            value = urlsafe_base64_encode_string(value)
        except Exception as e:
            msg = f"Error encoding response value {latest_data[0]}"
            return None, error_status(msg, e=e, log=logger.error)

        # Get nonce
        report_count, read_status = self.oracle.get_new_value_count_by_query_id(query_id)
        if report_count is None or not read_status.ok:
            return None, error_status(f"Unable to get nonce: {read_status.error}", log=logger.error)

        # Attempt to submit value
        logger.info("Sending submitValue transaction")
        submit_value_receipt, status = self.oracle.submit_value(
            query_id=query_id, value=value, nonce=report_count, query_data=query_data
        )
        if not status.ok:
            return None, error_status(f"Unable to submit value: {status.error}", log=logger.info)

        if submit_value_receipt == "failure":
            msg = "Submission transaction failed"
            return None, error_status(msg, log=logger.info)

        return submit_value_receipt, ResponseStatus()

    async def report(self, report_count: Optional[int] = None) -> None:
        """Submit values to Tellor oracles on an interval."""

        while report_count is None or report_count > 0:
            online = await self.is_online()
            if online:
                if self.has_native_token():
                    _, _ = await self.report_once()
            else:
                logger.warning("Unable to connect to the internet!")

            logger.info(f"Sleeping for {self.wait_period} seconds")
            await asyncio.sleep(self.wait_period)

            if report_count is not None:
                report_count -= 1
