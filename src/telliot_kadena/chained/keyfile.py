from typing import Dict
from typing import List

import nacl.pwhash
import nacl.secret
import nacl.utils
from nacl import encoding
from nacl import signing


# Derive a secret key from the password using argon2i
def encrypt(private_keys: List[str], password: str) -> List[Dict[str, str]]:
    """
    Encrypts a list of private keys with a given password.
    Returns a list of dictionaries containing the ciphertext, nonce, and salt for each private key.

    Args:
        - private_keys: A list of private keys to encrypt.
        - password: The password to use for encryption.

    Return: A list of dictionaries containing the ciphertext, nonce, and salt for each private key.
    """
    ciphertexts = []
    password_bytes = password.encode("utf-8")
    for private_key in private_keys:
        private_key_bytes = bytes.fromhex(private_key)
        salt = nacl.utils.random(nacl.pwhash.argon2i.SALTBYTES)
        nonce = nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE)
        key = nacl.pwhash.argon2i.kdf(nacl.secret.SecretBox.KEY_SIZE, password_bytes, salt)
        box = nacl.secret.SecretBox(key)
        ciphertext = box.encrypt(plaintext=private_key_bytes, nonce=nonce)
        ciphertexts.append({"ciphertext": ciphertext.ciphertext.hex(), "nonce": nonce.hex(), "salt": salt.hex()})
    return ciphertexts


def decrypt(encryptions: List[Dict[str, str]], password: str) -> List[str]:
    """
    Decrypts the given list of encryptions using the provided password.

    Args:
        encryptions (List[Dict[str, str]]): A list of dictionaries representing encrypted data.
            Each dictionary must contain the keys 'ciphertext', 'nonce', and 'salt'.
        password (str): The password used to encrypt the data.
    Returns:
        List[str]: A list of decrypted private keys.
    """
    decryptions = []
    password_bytes = password.encode("utf-8")
    for encryption in encryptions:
        salt = bytes.fromhex(encryption["salt"])
        ciphertext = bytes.fromhex(encryption["ciphertext"])
        nonce = bytes.fromhex(encryption["nonce"])
        key = nacl.pwhash.argon2i.kdf(nacl.secret.SecretBox.KEY_SIZE, password_bytes, salt)
        box = nacl.secret.SecretBox(key)
        decryptions.append(box.decrypt(ciphertext, nonce=nonce).hex())
    return decryptions


def restore_pub_key(seed: str) -> str:
    """Restores a public key from a seed string.

    Args:
        seed: A hexadecimal string representing the seed for the keypair.

    Returns:
        The public key for the keypair, as a string.

    Raises:
        ValueError: If the seed is not provided or has an invalid length.
    """
    if not seed:
        raise ValueError("seed for KeyPair generation not provided")
    if len(seed) != 64:
        raise ValueError("Seed for KeyPair generation has bad size")
    seed_for_nacl = bytes.fromhex(seed)
    kp = signing.SigningKey(seed_for_nacl)
    pub_key = kp.verify_key.encode(encoding.HexEncoder).decode()
    return pub_key


if __name__ == "__main__":
    print(encrypt(["f92089d02de9f01df0bf53c9d9d677dee960826640bc39f1c45234cc13d66683"], "123"))
    print(
        decrypt(
            [
                {
                    "ciphertext": "3812438618808dbcec7b1aa6ba062a600529856e77f1aa84815fc42ed5475b039772fe083b628f992f01068f0aabe54c",  # noqa: E501, B950
                    "nonce": "9fca509fbaf2cfb5296255b9694dd9c4b02fb3ff35ebb08f",
                    "salt": "396ae3cc0e6cba292b1dab5ecb739fb4",
                }
            ],
            "123",
        )
    )
    print(restore_pub_key("f92089d02de9f01df0bf53c9d9d677dee960826640bc39f1c45234cc13d66683"))
