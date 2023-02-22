import base64
import hashlib


def urlsafe_base64_decode_string(input_str: str) -> str:
    """
    Decodes a URL-safe base64-encoded string to its original form.

    Args:
        input_str: The URL-safe base64-encoded string to be decoded.

    Returns:
        The decoded string.

    """
    # Encode the input string to bytes using the UTF-8 encoding.
    input_bytes = input_str.encode()

    # Determine the number of padding characters that need to be added to make the input bytes multiple of 4 in length.
    # The padding characters are '=' characters added to the end of the encoded bytes to make the length multiple of 4.
    rem = len(input_bytes) % 4
    if rem > 0:
        input_bytes += b"=" * (4 - rem)

    # Use the URL-safe variant of the base64 decoding to decode the input bytes.
    decoded_bytes = base64.urlsafe_b64decode(input_bytes)

    # Decode the decoded bytes to obtain the original string.
    return decoded_bytes.decode()


def urlsafe_base64_encode_string(input_str: str) -> str:
    """
    Encodes the input string as a URL-safe base64-encoded string.

    Args:
        input_str: The string to be encoded.

    Returns:
        The input string encoded as a URL-safe base64-encoded string.

    """
    # Encode the input string to bytes using UTF-8 encoding.
    input_bytes = input_str.encode("utf-8")

    return urlsafe_base64_encode_bytes(input_bytes)


def urlsafe_base64_encode_bytes(input_bytes: bytes) -> str:
    """
    Encodes the input string as a URL-safe base64-encoded string.

    Args:
        input_str: The string to be encoded.

    Returns:
        The input string encoded as a URL-safe base64-encoded string.

    """

    # Use the URL-safe variant of the base64 encoding to encode the input bytes.
    encoded_bytes = base64.urlsafe_b64encode(input_bytes)

    # Remove any padding characters from the end of the encoded bytes.
    # This is necessary because some applications may not be able to handle padding characters.
    # The padding characters are '=' characters added to the end of the encoded bytes to make the length multiple of 4.
    # By removing the padding characters, we ensure that the length of the encoded string is always a multiple of 4.
    encoded_bytes_without_padding = encoded_bytes.rstrip(b"=")

    # Decode the encoded bytes to obtain the URL-safe base64-encoded string.
    return encoded_bytes_without_padding.decode()


def b64url_decode_arr(input: str) -> bytes:
    """
    Decodes a URL-safe base64-encoded string into bytes.

    Args:
        input: The URL-safe base64-encoded string to be decoded.

    Returns:
        The decoded bytes.

    """
    # Use the URL-safe variant of the base64 decoding to decode the input string.
    # padding characters are automatically handled here.
    return base64.urlsafe_b64decode(input)


def hash_bin(s: str) -> bytes:
    """
    Hashes a string using the Blake2b algorithm and returns the hash as bytes.

    Args:
        s: The string to be hashed.

    Returns:
        The hash of the input string as bytes.

    """
    # Compute the hash of the input string.
    h = hashlib.blake2b(digest_size=32)
    h.update(s.encode())
    return h.digest()


def hash(s: str) -> str:
    """
    Hashes a string using the Blake2b algorithm and URL-safe base64-encodes the resulting hash.

    Args:
        s: The string to be hashed and encoded.

    Returns:
        The URL-safe base64-encoded hash of the input string.

    """
    # Compute the hash of the input string.
    hash_bytes = hash_bin(s)

    # URL-safe base64-encode the hash bytes and return the result.
    return urlsafe_base64_encode_bytes(hash_bytes)


if __name__ == "__main__":
    print(urlsafe_base64_encode_string("100"))
    print(urlsafe_base64_decode_string("MS42Mjg1ZSsxOQ"))
    print(f"query data: {urlsafe_base64_encode_string('{SpotPrice: [kda,usd]}')}")
    print(urlsafe_base64_decode_string("e1Nwb3RQcmljZToge3RyYix1c2R9fQ"))
    print(hash("e1Nwb3RQcmljZToge3RyYix1c2R9fQ"))
