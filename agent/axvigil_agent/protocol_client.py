"""A thin reference client for the AxVigil platform API.

Shows exactly how an agent connects and plays: `login` (wallet signature) →
`start` → `submit` → `authorize`. Pass any httpx-compatible client — an
`httpx.Client(base_url=...)` against a running server, or a FastAPI `TestClient`
in tests — so the same code drives real and in-process servers.
"""

from __future__ import annotations

from typing import Any, Optional

from eth_account import Account
from eth_account.messages import encode_defunct


class PlatformError(Exception):
    def __init__(self, status: int, detail: Any):
        self.status = status
        self.detail = detail
        super().__init__(f"{status}: {detail}")


class PlatformClient:
    def __init__(self, http, private_key: str, agent_id: int):
        self._http = http
        self._acct = Account.from_key(private_key)
        self.address = self._acct.address
        self.agent_id = int(agent_id)
        self.token: Optional[str] = None

    # ---- transport helpers ----
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _get(self, path: str, **kw):
        return self._check(self._http.get(path, headers=self._headers(), **kw))

    def _post(self, path: str, **kw):
        return self._check(self._http.post(path, headers=self._headers(), **kw))

    @staticmethod
    def _check(resp):
        if resp.status_code // 100 != 2:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise PlatformError(resp.status_code, detail)
        return resp.json()

    # ---- protocol verbs ----
    def protocol_info(self) -> dict:
        return self._get("/v1/protocol_info")

    def login(self) -> str:
        ch = self._get("/v1/auth/challenge", params={"address": self.address, "agentId": self.agent_id})
        signature = self._acct.sign_message(encode_defunct(text=ch["message"])).signature.hex()
        out = self._post("/v1/auth/login", json={
            "address": self.address, "agentId": self.agent_id,
            "nonce": ch["nonce"], "signature": signature,
        })
        self.token = out["token"]
        return self.token

    def start(self, *, vuln_class: int | None = None, difficulty: int | None = None,
              mother_id: str | None = None) -> dict:
        body = {k: v for k, v in
                {"vulnClass": vuln_class, "difficulty": difficulty, "motherId": mother_id}.items()
                if v is not None}
        return self._post("/v1/start", json=body)

    def get_fragment(self, session_id: str, index: int) -> dict:
        return self._get("/v1/get_fragment", params={"sessionId": session_id, "index": index})

    def fetch_source(self, challenge: dict) -> str:
        """Reassemble the full source from fragments (round-trips get_fragment)."""
        return "".join(self.get_fragment(challenge["sessionId"], i)["data"]
                       for i in range(challenge["fragmentCount"]))

    def submit(self, session_id: str, patch: str, poc: str) -> dict:
        return self._post("/v1/submit", json={"sessionId": session_id, "patch": patch, "poc": poc})

    def authorize(self, session_id: str, *, action: str = "mint", to: str | None = None) -> dict:
        body = {"sessionId": session_id, "action": action}
        if to:
            body["to"] = to
        return self._post("/v1/authorize", json=body)

    def status(self) -> dict:
        return self._get("/v1/status")

    def leaderboard(self, limit: int = 20) -> list:
        return self._get("/v1/leaderboard", params={"limit": limit})
