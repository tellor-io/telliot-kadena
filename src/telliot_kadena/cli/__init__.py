from telliot_core.apps.core import NETWORKS

# 20 kadena chains
NETWORKS.update({num: "chain_web" for num in range(1, 20)})
