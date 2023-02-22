import time
from typing import Any
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional
from typing import Tuple

import requests
from requests.adapters import HTTPAdapter
from requests.adapters import Response
from requests.adapters import Retry
from telliot_core.utils.response import error_status
from telliot_core.utils.response import ResponseStatus
from telliot_feeds.utils.log import get_logger

from telliot_kadena.contracts import NAMESPACE
from telliot_kadena.model.chainweb_endpoints import ChainwebEndpoint
from telliot_kadena.utils.assemble_code import assemble_code
from telliot_kadena.utils.exec_cmd import mk_meta
from telliot_kadena.utils.exec_cmd import prepare_exec_cmd

logger = get_logger(__name__)

endpoint_type = Literal["local", "send", "poll"]


class Module:
    """Generic Module Class for interacting with Kadena Chainweb Modules

    Args:
    - endpoint (ChainwebEndpoint): Chainweb Endpoint
    - module_name (str): Name of the Module

    """

    def __init__(
        self,
        endpoint: ChainwebEndpoint,
        module_name: str,
    ):
        self.module_name = module_name
        self.rpc_api = endpoint.url  # https://api.testnet.chainweb.com/chainweb/0.0/
        self.network_id = endpoint.network  # testnet04
        self.explorer = endpoint.explorer
        self.chain_id = str(endpoint.chain_id)  # 1
        self.namespace = NAMESPACE[self.network_id]

    def endpoint(self, type: endpoint_type) -> str:
        """Returns the endpoint for the given type (local, send, poll)"""
        return f"{self.rpc_api}{type}"

    def mk_read_cmd(self, function_name: str, **kwargs: Any) -> Dict[str, Any]:
        """Returns a read command for the given function name and kwargs

        Args:
        - function_name (str): Name of the function to call
        - **kwargs (Any): Arguments to pass to the function

        """
        prep_code = assemble_code(function=f"{self.namespace}.{self.module_name}.{function_name}", **kwargs)
        return prepare_exec_cmd(pact_code=prep_code, meta=mk_meta(gas_limit=600, chain_id=str(self.chain_id)))

    def request(
        self, data: Dict[str, List[Dict[str, Any]]], endpoint_type: endpoint_type
    ) -> Tuple[Optional[Response], ResponseStatus]:
        """Sends a request to the given endpoint type (local, send, poll) and returns the response and status

        Args:
        - data (Dict[str, List[Dict[str, Any]]]): Data to send
        - endpoint_type (endpoint_type): Type of endpoint to send the request to

        Returns:
        - Tuple[Optional[Response], ResponseStatus]: Response and status
        """
        headers = {"Content-Type": "application/json"}
        url = self.endpoint(type=endpoint_type)
        retries = Retry(
            total=3, backoff_factor=calculate_backoff, status_forcelist=[500, 502, 503, 504, 400]  # type: ignore
        )
        with requests.Session() as session:
            session.mount("https://", HTTPAdapter(max_retries=retries))
            try:
                res = session.post(url, headers=headers, json=data)
                res.raise_for_status()
                return res, ResponseStatus()
            except requests.exceptions.HTTPError as e:
                note = f"HTTP Error Occured: {e}"
                return None, error_status(note=note, e=e, log=logger.error)
            except requests.exceptions.ConnectionError as e:
                note = f"Error Connecting: {e}"
                return None, error_status(note=note, e=e, log=logger.error)
            except requests.exceptions.Timeout as e:
                note = f"Timeout Error: {e}"
                return None, error_status(note=note, e=e, log=logger.error)
            except requests.exceptions.RequestException as e:
                note = f"Error: {e}"
                return None, error_status(note=note, e=e, log=logger.error)

    def fetch_receipt_with_retry(
        self, request_keys: dict[str, str], retry_count: int = 4
    ) -> Tuple[Optional[str], ResponseStatus]:
        """Fetch receipt from chainweb with retry logic

        Args:
        - Request keys from send request

        Returns: Receipt from chainweb
        """
        endpoint = self.endpoint(type="poll")
        headers = {"Content-Type": "application/json"}
        retries = Retry(
            total=retry_count, backoff_factor=calculate_backoff, status_forcelist=[500, 502, 503, 504]  # type: ignore
        )
        with requests.Session() as session:
            session.mount("https://", HTTPAdapter(max_retries=retries))
            try:
                response = session.post(endpoint, json=request_keys, headers=headers)
                response.raise_for_status()
                while response.json() == {} and retry_count > 0:
                    print("Fetching receipt from chainweb for confirmation...")
                    response = session.post(endpoint, json=request_keys, headers=headers)
                    response.raise_for_status()
                    retry_count -= 1
                    if retry_count > 0:
                        time.sleep(
                            calculate_backoff(retry_count)
                        )  # Wait for calculated backoff time before the next retry attempt
                if response.json() == {}:
                    return None, error_status(note="Unable to fetch receipt from API", log=logger.error)
                req_key = request_keys["requestKeys"][0]
                parse_receipt = self.parse_tx_receipt(req_key, response)
                logger.info(f"Link to receipt: {self.explorer}/tx/{req_key}")
                logger.info(f"Transaction status: {parse_receipt}")
                return parse_receipt, ResponseStatus()
            except requests.exceptions.HTTPError as e:
                note = f"HTTP Error Occured: {e}"
                return None, error_status(note=note, e=e, log=logger.error)
            except requests.exceptions.ConnectionError as e:
                note = f"Error Connecting: {e}"
                return None, error_status(note=note, e=e, log=logger.error)
            except requests.exceptions.Timeout as e:
                note = f"Timeout Error: {e}"
                return None, error_status(note=note, e=e, log=logger.error)
            except requests.exceptions.RequestException as e:
                note = f"Error: {e}"
                return None, error_status(note=note, e=e, log=logger.error)

    def read(self, function_name: str, **kwargs: Any) -> Tuple[Any, ResponseStatus]:
        data = self.mk_read_cmd(function_name, **kwargs)
        res, status = self.request(data=data, endpoint_type="local")
        if not status.ok or res is None:
            return None, status
        try:
            if res.json()["result"]["status"] == "success":
                return res.json()["result"]["data"], ResponseStatus()
            msg = res.json()["result"]["error"]["message"]
            return None, error_status(note=msg, log=logger.error)
        except Exception as e:
            return None, error_status(note="Error reading from chainweb", e=e, log=logger.error)

    def read_any_module(
        self, module_name_with_namespace: str, function_name: str, **kwargs: Any
    ) -> Tuple[Any, ResponseStatus]:
        """Read from any module in the chainweb

        Args:
        - module_name_with_namespace (str): Module name with namespace
        - function_name (str): Function name
        - **kwargs (Any): Arguments to pass to the function

        Returns:
        - Tuple[Any, ResponseStatus]: Response and status
        """
        prep_code = assemble_code(f"{module_name_with_namespace}.{function_name}", **kwargs)
        prep_cmd = prepare_exec_cmd(pact_code=prep_code, meta=mk_meta(gas_limit=600, chain_id=str(self.chain_id)))
        res, status = self.request(data=prep_cmd, endpoint_type="local")
        if not status.ok or res is None:
            return None, status
        try:
            if res.json()["result"]["status"] == "success":
                return res.json()["result"]["data"], ResponseStatus()
            msg = res.json()["result"]["error"]["message"]
            return None, error_status(note=msg, log=logger.error)
        except Exception as e:
            return None, error_status(note="Error reading from chainweb", e=e, log=logger.error)

    def parse_tx_receipt(self, request_key: str, tx_receipt: Response) -> str:
        """Parse transaction receipt

        Args: Transaction receipt

        Returns: Transaction status
        """
        status: str = tx_receipt.json()[request_key]["result"]["status"]
        return status


def calculate_backoff(retry_attempt: int) -> float:
    """Calculate backoff time for retry logic"""
    initial_backoff = 60
    backoff_factor = 2
    if retry_attempt == 1:
        return initial_backoff
    wait: float = initial_backoff / (backoff_factor ** (retry_attempt - 2))
    return wait
