import logging
from dataclasses import dataclass
from dataclasses import field
from typing import List
from typing import Optional

from telliot_core.apps.config import ConfigFile
from telliot_core.apps.config import ConfigOptions
from telliot_core.model.base import Base

from telliot_kadena import chainweb_api_version

logger = logging.getLogger(__name__)


@dataclass
class ChainwebEndpoint(Base):
    """Endpoint for Chainweb compatible network"""

    #: Chain ID
    chain_id: Optional[int] = None

    #: Network Name (e.g. 'mainnet', 'testnet')
    network: str = ""

    #: Provider Name (e.g. 'Kadena')
    provider: str = ""

    #: URL (e.g. 'https://api.chainweb.com/chainweb/{api_version}/mainnet01/chain/1/pact/api/v1/')
    url: str = ""

    #: Explorer URL ')
    explorer: Optional[str] = None


# api reference https://api.chainweb.com/openapi/pact.html
default_endpoint_list = [
    ChainwebEndpoint(
        chain_id=1,
        provider="Kadena",
        network="mainnet",
        url=f"https://api.chainweb.com/chainweb/{chainweb_api_version}/mainnet01/chain/1/pact/api/v1/",
        explorer="https://explorer.chainweb.com/mainnet",
    ),
    ChainwebEndpoint(
        chain_id=1,
        provider="Kadena",
        network="testnet04",
        url=f"https://api.testnet.chainweb.com/chainweb/{chainweb_api_version}/testnet04/chain/1/pact/api/v1/",
        explorer="https://explorer.chainweb.com/testnet",
    ),
]


@dataclass
class ChainwebEndpointList(ConfigOptions):
    endpoints: List[ChainwebEndpoint] = field(default_factory=lambda: default_endpoint_list)

    def get_chain_endpoint(self, chain_id: int = 1) -> Optional[ChainwebEndpoint]:
        """Get an Endpoint for the specified chain_id"""

        for endpoint in self.endpoints:
            if endpoint.chain_id == chain_id:
                return endpoint

        return None

    def find(
        self,
        *,
        chain_id: Optional[int] = None,
        network: Optional[str] = None,
    ) -> list[ChainwebEndpoint]:

        result = []
        for ep in self.endpoints:

            if chain_id is not None:
                if chain_id != ep.chain_id:
                    continue
            if network is not None:
                if network != ep.network:
                    continue

            result.append(ep)

        return result


if __name__ == "__main__":
    cf = ConfigFile(name="kadena-endpoints", config_type=ChainwebEndpointList, config_format="yaml")

    config_endpoints = cf.get_config()

    print(config_endpoints)
