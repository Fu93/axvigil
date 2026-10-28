import time
import pytest
from eth_account import Account
from fastapi.testclient import TestClient
from web3 import Web3
from backend.app import create_app
from backend.chain import Chain
from backend.crypto import MINT_FIELDS, sign, recover
from backend.signer import create_signer
from challenges.generator import generate, reference
from scripts.dev_chain import deploy
from verifier.worker import chain as anvil, grade


@pytest.fixture
def env(tmp_path):
    with anvil() as w:
        key = Account.create().key
        owner = w.eth.accounts[0]
        agent = Account.create()
        # Fund a randomly generated agent wallet; tests never use an external network.
        w.eth.send_transaction({"from": owner, "to": agent.address, "value": 10**19})
        registry = deploy(w, "MockAgentID", owner)
        skill = deploy(w, "AxVigilSkill", owner, registry.address, owner)
        nft = deploy(
            w,
            "AxVigilCollectible",
            owner,
            registry.address,
            skill.address,
            Account.from_key(key).address,
            owner,
            [5444, 1555, 622, 152, 4],
            50,
        )
        skill.functions.grantRole(
            Web3.keccak(text="MINTER_ROLE"), nft.address
        ).transact({"from": owner})
        nft.functions.commitSeed(Web3.keccak(text="test-seed")).transact(
            {"from": owner}
        )
        registry.functions.mintId(agent.address, 1).transact({"from": owner})
        c = Chain(w.provider.endpoint_uri, registry.address, nft.address, 31337)
        signer_client = TestClient(create_signer(c, key, "s" * 40))

        def issue(auth):
            r = signer_client.post(
                "/sign", json=auth, headers={"Authorization": "Bearer " + "s" * 40}
            )
            assert r.status_code == 200, r.text
            return r.json()["signature"]

        app = create_app(
            c, grader=grade, db_path=tmp_path / "state.sqlite", sign_request=issue
        )
        with TestClient(app) as client:
            yield client, c, agent, owner, key, app


def login(client, agent, agent_id=1):
    r = client.post(
        "/api/prepare", json={"wallet": agent.address, "agentId": str(agent_id)}
    )
    assert r.status_code == 200, r.text
    prep = r.json()
    body = {"nonce": prep["nonce"], "signature": sign(prep["typedData"], agent.key)}
    r = client.post("/api/login", json=body)
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}, body


def poll(client, tid, headers):
    for _ in range(400):
        r = client.get(f"/api/challenges/{tid}/status", headers=headers).json()
        if r["state"] not in ("grading", "calibrating"):
            return r
        time.sleep(0.05)
    raise AssertionError("Grader did not finish")


def signed_tx(c, agent, fn):
    tx = fn.build_transaction(
        {
            "from": agent.address,
            "nonce": c.w.eth.get_transaction_count(agent.address),
            "gas": 2000000,
        }
    )
    return c.w.eth.wait_for_transaction_receipt(
        c.w.eth.send_raw_transaction(agent.sign_transaction(tx).raw_transaction)
    )


def test_real_end_to_end_and_login_replay(env):
    client, c, agent, owner, key, app = env
    headers, body = login(client, agent)
    assert client.post("/api/login", json=body).status_code == 401
    assert client.post("/api/start", json={"vulnClass": 0}).status_code == 401
    r = client.post("/api/start", json={"vulnClass": 0}, headers=headers)
    assert r.status_code == 202, r.text
    tid = r.json()["challengeId"]
    assert poll(client, tid, headers)["state"] == "issued"
    fragment = client.get(f"/api/challenges/{tid}/fragments/0", headers=headers)
    assert fragment.status_code == 200 and "reference" not in fragment.json()
    with app.state.store.connect() as db:
        row = db.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
    challenge = generate(row["class"], int(row["seed"]))
    patch, poc = reference(challenge)
    r = client.post(
        f"/api/challenges/{tid}/submit",
        json={"patch": patch, "poc": poc},
        headers=headers,
    )
    assert r.status_code == 202, r.text
    assert poll(client, tid, headers)["state"] == "passed"
    assert (
        client.post("/api/start", json={"vulnClass": 1}, headers=headers).status_code
        == 409
    )
    r = client.post(f"/api/challenges/{tid}/authorize", headers=headers)
    assert r.status_code == 200, r.text
    response = r.json()
    auth = response["auth"]
    sig = response["signature"]
    assert isinstance(auth["nonce"], str)
    assert recover(response["typedData"], sig) == Account.from_key(key).address
    assert (
        client.post(f"/api/challenges/{tid}/authorize", headers=headers).json()["auth"]
        == auth
    )
    values = tuple(
        int(auth[n]) if t.startswith("uint") else auth[n] for n, t in MINT_FIELDS
    )
    receipt = signed_tx(c, agent, c.nft.functions.mint(values, sig))
    assert receipt.status == 1
    assert c.minted(1) == 1 and c.record(1)["totalSolves"] == 1
    assert signed_tx(c, agent, c.nft.functions.mint(values, sig)).status == 0
    assert (
        client.post(f"/api/challenges/{tid}/authorize", headers=headers).status_code
        == 409
    )
    assert client.get("/api/skills/1").json()["record"]["classMask"] == 1
    # Move Agent ID: stale API session loses access and the record follows the ID.
    registry = c.w.eth.contract(
        address=c.registry_address,
        abi=__import__("backend.chain", fromlist=["artifact"]).artifact("MockAgentID")[
            "abi"
        ],
    )
    assert (
        signed_tx(
            c, agent, registry.functions.transferFrom(agent.address, owner, 1)
        ).status
        == 1
    )
    assert (
        client.get(f"/api/challenges/{tid}/status", headers=headers).status_code == 403
    )
    assert c.skill.functions.ownerOf(1).call() == owner


def test_validation_rate_limit_and_cross_agent_access(env):
    client, c, agent, owner, key, app = env
    headers, _ = login(client, agent)
    assert client.get("/api/challenges/nope/status", headers=headers).status_code == 404
    assert (
        client.post("/api/start", json={"vulnClass": 3}, headers=headers).status_code
        == 422
    )
    assert client.post("/api/login", content=b"x" * 120001).status_code == 413
    assert (
        client.post(
            "/api/login", json={"nonce": "0x00", "signature": "0x00"}
        ).status_code
        == 401
    )
    assert client.get("/").status_code == 200
    assert (
        "frame-ancestors 'none'" in client.get("/").headers["content-security-policy"]
    )
    for _ in range(11):
        r = client.post("/api/prepare", json={"wallet": agent.address, "agentId": 1})
    assert r.status_code == 429


def test_signer_refuses_unauthorized_requests(env):
    _, c, agent, _, key, _ = env
    with TestClient(create_signer(c, key, "s" * 40)) as client:
        assert client.post("/sign", json={}).status_code == 401
        assert (
            client.post(
                "/sign", json={}, headers={"Authorization": "Bearer " + "s" * 40}
            ).status_code
            == 409
        )


def test_expiry_uint256_and_fail_closed_grader(env):
    client, c, agent, owner, key, app = env
    big_id = 2**128 + 123
    from backend.chain import artifact

    registry = c.w.eth.contract(
        address=c.registry_address, abi=artifact("MockAgentID")["abi"]
    )
    registry.functions.mintId(agent.address, big_id).transact({"from": owner})
    r = client.post(
        "/api/prepare", json={"wallet": agent.address, "agentId": str(big_id)}
    )
    assert r.status_code == 200
    assert r.json()["typedData"]["message"]["agentId"] == str(big_id)
    prep = r.json()
    with app.state.store.connect() as db:
        db.execute("UPDATE nonces SET deadline=0 WHERE nonce=?", (prep["nonce"],))
    assert (
        client.post(
            "/api/login",
            json={
                "nonce": prep["nonce"],
                "signature": sign(prep["typedData"], agent.key),
            },
        ).status_code
        == 401
    )
    headers, _ = login(client, agent)
    with app.state.store.connect() as db:
        db.execute("UPDATE sessions SET deadline=0")
    assert (
        client.post("/api/start", json={"vulnClass": 0}, headers=headers).status_code
        == 401
    )


def test_reference_failure_never_issues_challenge(env, tmp_path):
    _, c, agent, _, _, _ = env

    def forged(payload):
        return {"passed": True}  # no matching hash, class or trusted checks

    app = create_app(c, grader=forged, db_path=tmp_path / "reject.sqlite")
    with TestClient(app) as client:
        headers, _ = login(client, agent)
        r = client.post("/api/start", json={"vulnClass": 1}, headers=headers)
        tid = r.json()["challengeId"]
        assert poll(client, tid, headers)["state"] == "error"
        assert (
            client.get(
                f"/api/challenges/{tid}/fragments/0", headers=headers
            ).status_code
            == 409
        )
        assert (
            client.post(f"/api/challenges/{tid}/authorize", headers=headers).status_code
            == 409
        )
