import json
import time
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from nacl.signing import SigningKey

from telliot_kadena.utils.assemble_code import assemble_code
from telliot_kadena.utils.encoding import hash_bin
from telliot_kadena.utils.encoding import urlsafe_base64_encode_bytes


def sign_msg(msg: str, key_pair: Dict[str, str]) -> Dict[str, Any]:
    """
    Sign a message using a secret key and return the signature and public key.

    Args:
        msg: The message to sign, as a bytes object.
        key_pair: A dictionary containing the secret key and public key as hex-encoded strings.

    Returns:
        A dictionary containing the hash of the message, the signature as a hex-encoded string,
        and the public key as a bytes object.

    """
    pk = key_pair.get("public_key")
    sk = key_pair.get("secret_key")
    if not pk or not sk:
        raise TypeError("Invalid key pair: expected to find 'public_key' and 'secret_key' keys.")

    hsh_bin = hash_bin(msg)
    hsh = urlsafe_base64_encode_bytes(hsh_bin)
    secret_key = SigningKey(bytes.fromhex(key_pair["secret_key"]))
    sig_bin = secret_key.sign(hsh_bin).signature
    return {"hash": hsh, "sig": sig_bin.hex(), "pub_key": bytes.fromhex(key_pair["public_key"])}


def attach_sig(msg: str, kp_array: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """
    Attach signatures to a message using an array of key pairs and return the list of signatures.

    Args:
        msg: The message to sign, as a bytes object.
        kp_array: A list of dictionaries, where each dictionary contains the secret key and public key
            as hex-encoded strings.

    Returns:
        A list of dictionaries containing the hash of the message, the signature as a hex-encoded string
        or None if the key pair is invalid, and the public key as a bytes object.

    """
    hsh_bin = hash_bin(msg)
    hsh = urlsafe_base64_encode_bytes(hsh_bin)
    if len(kp_array) == 0:
        # If the key pair array is empty, return a list with a single dictionary containing the hash and no signature.
        return [{"hash": hsh, "sig": None}]
    else:
        # If the key pair array is not empty, iterate over the array and sign the message using each key pair.
        # If a key pair is invalid, attach a None signature to the message.
        return list(
            map(
                lambda kp: sign_msg(msg, kp)
                if kp.get("public_key") and kp.get("secret_key")
                else {"hash": hsh, "sig": None, "public_key": kp["public_key"]},
                kp_array,
            )
        )


def mk_meta(
    sender: str = "",
    chain_id: str = "0",
    gas_price: float = 0.0,
    gas_limit: int = 0,
    creation_time: Optional[int] = None,
    ttl: int = 1800,
) -> Dict[str, Union[str, int, float]]:
    """
    Returns a metadata dictionary containing the specified values, with type enforcement for the values.

    Args:
        sender: The account address of the transaction sender (default is an empty string).
        chain_id: The chain identifier (default is '0').
        gas_price: The gas price for the transaction (default is 0.0).
        gas_limit: The maximum amount of gas that can be used for the transaction (default is 0).
        creation_time: The timestamp for when the transaction is created (default is the current time).
        ttl: The maximum number of seconds that the transaction will be valid (default is 1800).

    Returns:
        A dictionary containing metadata for the transaction, with enforced types for the values.
    """
    if creation_time is None:
        creation_time = int(time.time())

    assert isinstance(sender, str), "Expected sender to be a string"
    assert isinstance(chain_id, str), "Expected chain_id to be a string"
    assert isinstance(gas_price, (float, int)), "Expected gas_price to be a float or int"
    assert isinstance(gas_limit, int), "Expected gas_limit to be an int"
    assert isinstance(creation_time, int), "Expected creation_time to be an int"
    assert isinstance(ttl, int), "Expected ttl to be an int"

    return {
        "creationTime": creation_time,
        "ttl": ttl,
        "gasLimit": gas_limit,
        "chainId": chain_id,
        "gasPrice": gas_price,
        "sender": sender,
    }


def make_list(value: Any) -> List[Any]:
    """
    Ensure that the given value is a list. If it is already a list, return it unchanged.
    Otherwise, wrap it in a list and return that.

    Args:
        value: The value to be converted to a list.

    Returns:
        A list containing the given value.
    """
    return value if isinstance(value, list) else [value]


def pull_sig(s: Dict[str, str]) -> Dict[str, str]:
    """
    Extracts the signature from a dictionary.

    Args:
        s (dict): The dictionary containing the signature.

    Returns:
        dict: A dictionary with only the signature.

    Raises:
        TypeError: If the signature is not found in the input dictionary.
    """
    if "sig" not in s:
        raise TypeError("Expected to find keys of name 'sig' in " + str(s))
    return {"sig": s["sig"]}


def pull_and_check_hashes(sigs: List[Dict[str, Any]]) -> Any:
    """
    Extracts the hash from the first signature in the list of signature objects and checks that all signatures
    in the list have the same hash. Returns the hash.

    Args:
        sigs: A list of signature objects.

    Returns:
        The hash value as a string.

    Raises:
        TypeError: If the list of signatures is empty or contains signatures with different hash values.
    """
    if not sigs:
        raise TypeError("List of signatures is empty.")
    hsh = sigs[0]["hash"]
    for sig in sigs[1:]:
        if sig["hash"] != hsh:
            raise TypeError("Sigs for different hashes found: " + str(sigs))
    return hsh


def mk_single_cmd(sigs: List[Dict[str, Any]], cmd: str) -> Dict[str, Any]:
    """
    Create a single command object from a list of signatures and a command.

    Args:
        sigs (List[Dict[str, str]]): The list of signature objects.
        cmd (str): The command.

    Returns:
        Dict[str, any]: The command object with hashes, signatures, and the command.
    """
    assert isinstance(sigs, list), "Expected 'sigs' to be a list"
    assert isinstance(cmd, str), "Expected 'cmd' to be a string"

    return {
        "hash": pull_and_check_hashes(sigs),
        "sigs": list(map(pull_sig, filter(lambda sig: sig["sig"], sigs))),
        "cmd": cmd,
    }


def mk_signer(kp: Dict[str, Any]) -> Dict[str, Any]:
    """
    Args:
        - kp (Dict[str, Any]): Key pair dictionary containing the public key and optional clist

    Returns:
        - Dict[str, Any]: Signer object containing the public key and optional clist
    """
    signer = {"pubKey": kp["public_key"]}
    if "clist" in kp and kp["clist"]:
        signer["clist"] = make_list(kp["clist"])
    return signer


def formatted_time() -> str:
    """Returns the current time in ISO 8601 format, with a UTC timezone offset.

    Returns:
        A string in the format of "YYYY-MM-DDTHH:MM:SS.ssssss UTC"
    """
    return datetime.utcnow().isoformat() + " UTC"


def prepare_exec_cmd(
    pact_code: str,
    meta: Dict[str, Union[str, int, float]],
    nonce: Optional[str] = None,
    key_pairs: Optional[List[Dict[str, str]]] = None,
    env_data: Optional[Dict[str, str]] = None,
    network_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Prepares a command to execute a Pact code on chainweb.

    Args:
        pact_code (str): The Pact code to be executed.
        meta (Dict[str, str]): The metadata associated with the command.
        key_pairs (List[Dict[str, str]], optional): The list of key pairs used to sign the command.
        nonce (str, optional): The nonce associated with the command. Defaults to the current UTC time.
        env_data (Dict, optional): The environmental data to be passed to the Pact code. Defaults to None.
        network_id (str, optional): The network ID on which the command will be executed. Defaults to None.

    Returns:
        Dict[str, any]: A dictionary containing the signed command.
    """
    if nonce is None:
        nonce = formatted_time()
    assert isinstance(nonce, str), "Expected 'nonce' to be a string"
    assert isinstance(pact_code, str), "Expected 'pact_code' to be a string"
    kp_array = make_list(key_pairs or [])
    signers = list(map(mk_signer, kp_array))
    cmd_json = {
        "networkId": network_id,
        "payload": {"exec": {"data": env_data or None, "code": pact_code}},
        "signers": signers,
        "meta": meta,
        "nonce": nonce,
    }
    cmd = json.dumps(cmd_json, separators=(",", ":"))
    sigs = attach_sig(cmd, kp_array)
    return mk_single_cmd(sigs, cmd)


def mk_public_send(cmds: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Returns a dictionary representing a public send transaction with the given commands.

    Args:
        cmds: A list of commands to include in the transaction.

    Returns:
        A dictionary with a single key-value pair, where the key is "cmds" and the value is a list of commands.
    """
    return {"cmds": make_list(cmds)}


def simple_exec_cmd(
    pact_code: str,
    meta: Dict[str, Union[str, int, float]],
    key_pairs: List[Dict[str, Any]],
    env_data: Dict[str, Any],
    network_id: str,
    nonce: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Compose an exec command payload.

    Args:
        pact_code: The Pact code to execute.
        meta: A dictionary of meta data associated with the command.
        key_pairs: A list of key pairs to sign the command with.
        nonce: A unique identifier for the command.
        env_data: A dictionary of data to be used as input for the Pact code.
        network_id: The ID of the Pact network to send the command to.

    Returns:
        A dictionary representing the public send payload.
    """
    if nonce is None:
        nonce = formatted_time()
    return mk_public_send(
        prepare_exec_cmd(
            key_pairs=key_pairs, nonce=nonce, pact_code=pact_code, env_data=env_data, meta=meta, network_id=network_id
        )
    )


if __name__ == "__main__":
    # Example
    # submit value function in tellorflex: (defun submit-value (queryId value nonce queryData staker))
    prep_code = assemble_code(
        function="free.tellorflex.submit-value",
        queryId="EWnklLBmDXxZh0jXcOHS7xoFwA6aWvle7NmnkvQIp_w",
        value="OTYxNzgyMDAwMDAwMDAwMDAw",
        nonce=0,
        queryData="e1Nwb3RQcmljZTogW2tkYSx1c2RdfQ",
        staker="reporter",
    )
    exec_cmd = simple_exec_cmd(
        key_pairs=[
            {
                "public_key": "22c88bcd8a0e4d490f3d69761f42540e917e1b9efc88508e1db700c18a194573",
                "secret_key": "e801be41519661288dc8c3aa704708391ac4a3fdfea6bfd6b7a5ae2027c0d407",
                "clist": [
                    {
                        "args": ["reporter", "tellorflex", 10.0],
                        "name": "n_61b7d03ff34ca7e599e3551df8dcd4a3c1bf7524.f-TRB.TRANSFER",
                    },
                    {"args": [], "name": "coin.GAS"},
                    {"args": ["reporter"], "name": "n_61b7d03ff34ca7e599e3551df8dcd4a3c1bf7524.tellorflex.STAKER"},
                ],
            }
        ],
        pact_code=prep_code,
        env_data={
            "amount": 10,
            "keyset": {
                "pred": "keys-all",
                "keys": ["22c88bcd8a0e4d490f3d69761f42540e917e1b9efc88508e1db700c18a194573"],
            },
            "reporter": "reporter",
        },
        meta=mk_meta(sender="reporter", chain_id="1", gas_limit=150000, ttl=1800, gas_price=1e-7),
        network_id="testnet04",
    )
    print(exec_cmd)
