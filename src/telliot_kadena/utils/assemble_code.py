from typing import Any

from telliot_kadena.utils.encoding import hash
from telliot_kadena.utils.encoding import urlsafe_base64_encode_string


def assemble_code(function: str, **kwargs: Any) -> str:
    """
    Assemble a Pact code snippet from a function name and keyword arguments.

    Args:
        function: The name of the Pact function to call.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        A string containing the assembled Pact code.

    """
    formatted_args = []
    for _, value in kwargs.items():
        if isinstance(value, str):
            formatted_args.append(f'"{value}"')
        else:
            formatted_args.append(str(value))
    return f"({function} {' '.join(formatted_args)})"


if __name__ == "__main__":
    SPOT_PRICE_QUERY = "{SpotPrice: [kda,usd]}"
    query_id = hash(urlsafe_base64_encode_string(SPOT_PRICE_QUERY))
    query_data = urlsafe_base64_encode_string(SPOT_PRICE_QUERY)
    value = urlsafe_base64_encode_string(str(961782000000000000))
    print(
        assemble_code(
            "free.tellorflex.submit-value",
            queryId=query_id,
            value=value,
            nonce=0,
            queryData=query_data,
            staker="reporter1",
        )
    )
