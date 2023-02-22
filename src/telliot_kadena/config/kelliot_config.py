"""Adapted from https://github.com/tellor-io/telliot-core/blob/main/src/telliot_core/apps/telliot_config.py
"""
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Literal
from typing import Optional
from typing import Union

from telliot_core.apps.config import ConfigFile
from telliot_core.apps.config import ConfigOptions
from telliot_core.model.base import Base

from telliot_kadena.model.chainweb_endpoints import ChainwebEndpoint
from telliot_kadena.model.chainweb_endpoints import ChainwebEndpointList


@dataclass
class KelliotMainConfig(ConfigOptions):
    """Main telliot_core configuration object"""

    #: Control application logging level
    loglevel: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    #: Select chain id
    chain_id: int = 1

    network: Literal["testnet04", "mainnet"] = "testnet04"


@dataclass
class KelliotConfig(Base):

    main: KelliotMainConfig = field(default_factory=KelliotMainConfig)

    config_dir: Optional[Union[str, Path]] = None

    endpoints: ChainwebEndpointList = field(default_factory=ChainwebEndpointList)

    # Private storage for config files
    _ep_config_file: Optional[ConfigFile] = None

    def __post_init__(self) -> None:
        self._ep_config_file = ConfigFile(
            name="kadena-endpoints",
            config_type=ChainwebEndpointList,
            config_format="yaml",
            config_dir=self.config_dir,
        )

        self.endpoints = self._ep_config_file.get_config()

    def get_endpoint(self) -> ChainwebEndpoint:
        """Search endpoints for current chain_id"""
        eps = self.endpoints.find(network=self.main.network, chain_id=self.main.chain_id)
        if len(eps) > 0:
            return eps[0]
        else:
            raise ValueError(f"Endpoint not found for chain_id={self.main.chain_id}")
