# telliot-kadena
```sh
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

Initialize configuration
```sh
kadena config init
or
kadena config show
```

Add keyset to the keystore:
```sh
# example
kadena keyset add  <acct-nm> "<private-key> <private-key>" <predicate ie. keys-all> <chain-id>
# modules are only available on chain 1 for now
```

Report random Spot prices
```sh
kadena report --account <acct-nm> --network testnet04
```

Select an available spot price
```sh
# example
# To search available spots add '--help' to the command
kadena report --account <acct-nm> --network testnet04 --query-tag eth-usd-spot
```

Or build query for manual price submission
```sh
 kadena report --account <acct-nm> --network testnet04 --build-spot
 ```

Gas setting flags
'--gas-limit', '--gas-price'

See all options by using: '--help' flag

Note: keyset name has to be same as gas account
