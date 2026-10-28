from eth_account import Account
from eth_account.messages import encode_typed_data

MINT_FIELDS = [
    ("agentId", "uint256"),
    ("to", "address"),
    ("vulnClass", "uint8"),
    ("difficulty", "uint8"),
    ("pool", "uint8"),
    ("submissionHash", "bytes32"),
    ("nonce", "uint256"),
    ("deadline", "uint256"),
]


def typed_data(chain_id, contract, primary, fields, message):
    return {
        "types": {
            "EIP712Domain": [
                {"name": n, "type": t}
                for n, t in [
                    ("name", "string"),
                    ("version", "string"),
                    ("chainId", "uint256"),
                    ("verifyingContract", "address"),
                ]
            ],
            primary: [{"name": n, "type": t} for n, t in fields],
        },
        "primaryType": primary,
        "domain": {
            "name": "AxVigil",
            "version": "1",
            "chainId": chain_id,
            "verifyingContract": contract,
        },
        "message": message,
    }


def recover(data, signature):
    return Account.recover_message(
        encode_typed_data(full_message=data), signature=signature
    )


def sign(data, key):
    return (
        "0x"
        + Account.sign_message(
            encode_typed_data(full_message=data), key
        ).signature.hex()
    )
