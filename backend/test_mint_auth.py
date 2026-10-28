import json
import os
import tempfile
import unittest
from pathlib import Path

from eth_account import Account
from eth_account.messages import encode_typed_data

from backend.mint_auth import build_typed_data, sign_authorization


class MintAuthTest(unittest.TestCase):
    def test_signature_recovers_and_binds_submission_hash(self) -> None:
        private_key = "0x" + "11" * 32
        auth = {
            "agentId": 7,
            "to": "0x00000000000000000000000000000000000000AA",
            "vulnClass": 0,
            "difficulty": 1,
            "pool": 0,
            "submissionHash": "0x" + "22" * 32,
            "nonce": 3,
            "deadline": 1_900_000_000,
        }
        typed = build_typed_data(
            chain_id=97,
            verifying_contract="0x00000000000000000000000000000000000000BB",
            auth=auth,
        )
        signer, signature = sign_authorization(private_key, typed)
        recovered = Account.recover_message(encode_typed_data(full_message=typed), signature=signature)
        self.assertEqual(recovered, signer)
        self.assertEqual(signer, Account.from_key(private_key).address)

        tampered = json.loads(json.dumps(typed))
        tampered["message"]["submissionHash"] = "0x" + "33" * 32
        tampered_signable = encode_typed_data(full_message=tampered)
        self.assertNotEqual(
            Account.recover_message(tampered_signable, signature=signature),
            signer,
        )


if __name__ == "__main__":
    unittest.main()
