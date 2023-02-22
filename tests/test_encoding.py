from telliot_kadena.utils.encoding import urlsafe_base64_decode_string
from telliot_kadena.utils.encoding import urlsafe_base64_encode_string


def test_data_encode() -> None:
    """Tests the urlsafe_base64_encode_string and urlsafe_base64_decode_string functions."""
    # Test encoding and decoding a simple string
    encode_hello = urlsafe_base64_encode_string("hello")
    decode_hello = urlsafe_base64_decode_string(encode_hello)
    assert "hello" == decode_hello, "urlsafe_base64_encode_string and urlsafe_base64_decode_string should be inverses"

    # Test encoding and decoding a more complex string
    spec = "{SpotPrice: [kda,usd]}"
    encode_query_data = urlsafe_base64_encode_string(spec)
    decode_query_data = urlsafe_base64_decode_string(encode_query_data)
    assert spec == decode_query_data, "urlsafe_base64_encode_string and urlsafe_base64_decode_string should be inverses"
