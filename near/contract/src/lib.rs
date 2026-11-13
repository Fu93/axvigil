//! AxVigil evidence record on NEAR.
//!
//! The contract does not re-run Foundry. The off-chain AxVigil verifier produces
//! a `submissionHash` (keccak of the canonical challenge, seed, patch, and PoC)
//! and a sha256 of the canonical grade seal. This contract stores those two
//! hashes, opens a challenge window, and moves reputation when the window closes
//! or the resolver upholds a challenge.
//!
//! A function-call access key limited to `anchor_evidence` is a protocol rule,
//! not a check in this file. The contract only accepts an anchor from a
//! registered predecessor, so that key can publish a claim for its own account
//! and cannot name a different agent.

use near_sdk::borsh::{BorshDeserialize, BorshSerialize};
use near_sdk::store::LookupMap;
use near_sdk::{env, near, require, AccountId, NearToken, PanicOnDefault, Promise};

const SECOND_NS: u64 = 1_000_000_000;
const MIN_WINDOW_SECONDS: u64 = 1;
const MAX_WINDOW_SECONDS: u64 = 30 * 24 * 60 * 60;
const MAX_RESPONSE_SECONDS: u64 = 30 * 24 * 60 * 60;
const NUM_CLASSES: u8 = 3;
const NUM_DIFFICULTIES: u8 = 3;
const SPEC: &str = "axvigil-record/1";

#[derive(BorshDeserialize, BorshSerialize, Clone, Copy, PartialEq, Eq, Debug)]
#[borsh(crate = "near_sdk::borsh")]
enum RecordStatus {
    Pending,
    Challenged,
    Final,
    Revoked,
}

impl RecordStatus {
    fn as_str(self) -> &'static str {
        match self {
            Self::Pending => "Pending",
            Self::Challenged => "Challenged",
            Self::Final => "Final",
            Self::Revoked => "Revoked",
        }
    }
}

#[derive(BorshDeserialize, BorshSerialize, Clone, Debug)]
#[borsh(crate = "near_sdk::borsh")]
struct Record {
    agent: AccountId,
    evidence_hash: String,
    bundle_sha256: String,
    vuln_class: u8,
    difficulty: u8,
    status: RecordStatus,
    ready_at_ns: u64,
    respond_by_ns: u64,
    challenger: Option<AccountId>,
    challenge_hash: Option<String>,
    operator_bond: u128,
    challenge_bond: u128,
}

#[derive(BorshDeserialize, BorshSerialize, Clone, Debug)]
#[borsh(crate = "near_sdk::borsh")]
struct Reputation {
    registered: bool,
    banned: bool,
    pending: u32,
    finalized: u32,
    revoked: u32,
    records: Vec<String>,
}

impl Reputation {
    fn fresh() -> Self {
        Self {
            registered: true,
            banned: false,
            pending: 0,
            finalized: 0,
            revoked: 0,
            records: Vec::new(),
        }
    }

    fn is_valid(&self) -> bool {
        self.registered && !self.banned && self.finalized > 0
    }
}

#[near(contract_state)]
#[derive(PanicOnDefault)]
pub struct Contract {
    owner: AccountId,
    resolver: AccountId,
    response_ns: u64,
    operator_bond: u128,
    challenge_bond: u128,
    records: LookupMap<String, Record>,
    reputation: LookupMap<AccountId, Reputation>,
    claimable: LookupMap<AccountId, u128>,
    escrow: u128,
    claimable_total: u128,
}

#[near(serializers = [json])]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RecordView {
    pub agent: AccountId,
    pub evidence_hash: String,
    pub bundle_sha256: String,
    pub vuln_class: u8,
    pub difficulty: u8,
    pub status: String,
    pub ready_at_ns: String,
    pub respond_by_ns: String,
    pub challenger: Option<AccountId>,
    pub challenge_hash: Option<String>,
    pub operator_bond_yocto: String,
    pub challenge_bond_yocto: String,
    pub passed_claim: bool,
}

#[near(serializers = [json])]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ReputationView {
    pub account: AccountId,
    pub registered: bool,
    pub banned: bool,
    pub pending: u32,
    pub finalized: u32,
    pub revoked: u32,
    pub is_valid: bool,
    pub records: Vec<String>,
}

#[near(serializers = [json])]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ConfigView {
    pub spec: String,
    pub owner: AccountId,
    pub resolver: AccountId,
    pub response_seconds: u64,
    pub operator_bond_yocto: String,
    pub challenge_bond_yocto: String,
}

#[near(serializers = [json])]
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct AccountingView {
    pub escrow_yocto: String,
    pub claimable_total_yocto: String,
}

#[near]
impl Contract {
    /// `response_seconds` is how long a challenge stays open before anyone may
    /// expire it. Bonds are exact yoctoNEAR amounts, fixed for the life of the
    /// contract. Use `"0"` for a demo that does not lock tokens.
    #[init]
    pub fn new(
        response_seconds: u64,
        operator_bond_yocto: String,
        challenge_bond_yocto: String,
    ) -> Self {
        require!(
            (1..=MAX_RESPONSE_SECONDS).contains(&response_seconds),
            "response window out of range"
        );
        let owner = env::predecessor_account_id();
        Self {
            owner: owner.clone(),
            resolver: owner,
            response_ns: response_seconds
                .checked_mul(SECOND_NS)
                .expect("response window overflow"),
            operator_bond: parse_yocto(&operator_bond_yocto),
            challenge_bond: parse_yocto(&challenge_bond_yocto),
            records: LookupMap::new(b"r"),
            reputation: LookupMap::new(b"p"),
            claimable: LookupMap::new(b"c"),
            escrow: 0,
            claimable_total: 0,
        }
    }

    pub fn set_resolver(&mut self, resolver: AccountId) {
        self.assert_owner();
        self.resolver = resolver;
    }

    /// The predecessor account becomes the agent. One registration per account.
    pub fn register_agent(&mut self) {
        let agent = env::predecessor_account_id();
        require!(!self.is_registered(&agent), "already registered");
        self.reputation.insert(agent.clone(), Reputation::fresh());
        emit(
            "register_agent",
            serde_json::json!({ "agent": agent.as_str() }),
        );
    }

    /// Record a seal the caller claims has `passed == true`, and open the window.
    /// `evidence_hash` is the AxVigil `submissionHash` without the `0x` prefix.
    /// `bundle_sha256` is sha256 of the canonical grade JSON. This method does
    /// not see the JSON, so a false `passed` claim is caught by challenge, not here.
    #[payable]
    pub fn anchor_evidence(
        &mut self,
        evidence_hash: String,
        bundle_sha256: String,
        vuln_class: u8,
        difficulty: u8,
        window_seconds: u64,
        passed: bool,
    ) {
        let agent = env::predecessor_account_id();
        require!(self.is_registered(&agent), "not registered");
        require!(!self.is_banned(&agent), "agent is banned");
        require!(passed, "refusing a failing grade");
        require!(vuln_class < NUM_CLASSES, "invalid vulnerability class");
        require!(difficulty < NUM_DIFFICULTIES, "invalid difficulty");
        require!(
            (MIN_WINDOW_SECONDS..=MAX_WINDOW_SECONDS).contains(&window_seconds),
            "window out of range"
        );
        let evidence_hash = normalize_hash("evidence hash", &evidence_hash);
        let bundle_sha256 = normalize_hash("bundle hash", &bundle_sha256);
        require!(self.records.get(&evidence_hash).is_none(), "record exists");
        let deposit = env::attached_deposit().as_yoctonear();
        require!(
            deposit == self.operator_bond,
            "attached deposit must equal the operator bond"
        );

        let now = env::block_timestamp();
        let ready_at_ns = now
            .checked_add(
                window_seconds
                    .checked_mul(SECOND_NS)
                    .expect("window overflow"),
            )
            .expect("ready_at overflow");
        let record = Record {
            agent: agent.clone(),
            evidence_hash: evidence_hash.clone(),
            bundle_sha256: bundle_sha256.clone(),
            vuln_class,
            difficulty,
            status: RecordStatus::Pending,
            ready_at_ns,
            respond_by_ns: 0,
            challenger: None,
            challenge_hash: None,
            operator_bond: deposit,
            challenge_bond: 0,
        };
        self.records.insert(evidence_hash.clone(), record);
        self.lock(deposit);
        self.bump_rep(&agent, |rep| {
            rep.pending = rep.pending.checked_add(1).expect("pending overflow");
            rep.records.push(evidence_hash.clone());
        });
        emit(
            "anchor_evidence",
            serde_json::json!({
                "agent": agent.as_str(),
                "evidence_hash": evidence_hash,
                "bundle_sha256": bundle_sha256,
                "vuln_class": vuln_class,
                "difficulty": difficulty,
                "ready_at_ns": ready_at_ns.to_string(),
            }),
        );
    }

    /// Anyone except the agent may challenge a pending record before `ready_at`.
    /// `challenge_hash` is the challenger's counter-evidence digest (32-byte hex).
    #[payable]
    pub fn challenge(&mut self, evidence_hash: String, challenge_hash: String) {
        let challenger = env::predecessor_account_id();
        let evidence_hash = normalize_hash("evidence hash", &evidence_hash);
        let challenge_hash = normalize_hash("challenge hash", &challenge_hash);
        let mut record = self.take_record(&evidence_hash);
        require!(record.status == RecordStatus::Pending, "not pending");
        require!(
            challenger != record.agent,
            "agent cannot challenge own record"
        );
        require!(
            env::block_timestamp() < record.ready_at_ns,
            "challenge window closed"
        );
        let deposit = env::attached_deposit().as_yoctonear();
        require!(
            deposit == self.challenge_bond,
            "attached deposit must equal the challenge bond"
        );
        record.status = RecordStatus::Challenged;
        record.challenger = Some(challenger.clone());
        record.challenge_hash = Some(challenge_hash.clone());
        record.challenge_bond = deposit;
        record.respond_by_ns = env::block_timestamp()
            .checked_add(self.response_ns)
            .expect("respond_by overflow");
        let respond_by_ns = record.respond_by_ns;
        self.records.insert(evidence_hash.clone(), record);
        self.lock(deposit);
        emit(
            "challenge",
            serde_json::json!({
                "evidence_hash": evidence_hash,
                "challenger": challenger.as_str(),
                "challenge_hash": challenge_hash,
                "respond_by_ns": respond_by_ns.to_string(),
            }),
        );
    }

    /// Resolver only. `upheld` revokes the pending solve and pays the challenger
    /// both bonds. A rejection returns the record to pending and pays the
    /// challenge bond to the owner. The contract does not re-grade the seal.
    pub fn resolve_challenge(&mut self, evidence_hash: String, upheld: bool) {
        self.assert_resolver();
        let evidence_hash = normalize_hash("evidence hash", &evidence_hash);
        let mut record = self.take_record(&evidence_hash);
        require!(record.status == RecordStatus::Challenged, "not challenged");
        let challenger = record
            .challenger
            .clone()
            .expect("challenged record has a challenger");
        let challenge_bond = record.challenge_bond;
        if upheld {
            let operator_bond = record.operator_bond;
            record.status = RecordStatus::Revoked;
            record.operator_bond = 0;
            record.challenge_bond = 0;
            let agent = record.agent.clone();
            self.records.insert(evidence_hash.clone(), record);
            let payout = operator_bond
                .checked_add(challenge_bond)
                .expect("payout overflow");
            self.credit(&challenger, payout);
            self.bump_rep(&agent, |rep| {
                rep.pending = rep.pending.checked_sub(1).expect("pending underflow");
                rep.revoked = rep.revoked.checked_add(1).expect("revoked overflow");
            });
            emit(
                "revoke",
                serde_json::json!({
                    "evidence_hash": evidence_hash,
                    "agent": agent.as_str(),
                }),
            );
        } else {
            record.status = RecordStatus::Pending;
            record.challenger = None;
            record.challenge_hash = None;
            record.challenge_bond = 0;
            record.respond_by_ns = 0;
            self.records.insert(evidence_hash.clone(), record);
            self.credit(&self.owner.clone(), challenge_bond);
            emit(
                "challenge_rejected",
                serde_json::json!({ "evidence_hash": evidence_hash }),
            );
        }
    }

    /// After the response window, anyone may clear a challenge the resolver
    /// never answered. The challenger's bond is returned. The record is pending
    /// again, so another challenge can be filed while the original window is open.
    pub fn expire_challenge(&mut self, evidence_hash: String) {
        let evidence_hash = normalize_hash("evidence hash", &evidence_hash);
        let mut record = self.take_record(&evidence_hash);
        require!(record.status == RecordStatus::Challenged, "not challenged");
        require!(
            env::block_timestamp() >= record.respond_by_ns,
            "response window still open"
        );
        let challenger = record
            .challenger
            .clone()
            .expect("challenged record has a challenger");
        let challenge_bond = record.challenge_bond;
        record.status = RecordStatus::Pending;
        record.challenger = None;
        record.challenge_hash = None;
        record.challenge_bond = 0;
        record.respond_by_ns = 0;
        self.records.insert(evidence_hash.clone(), record);
        self.credit(&challenger, challenge_bond);
        emit(
            "challenge_expired",
            serde_json::json!({ "evidence_hash": evidence_hash }),
        );
    }

    /// After the challenge window, with no open challenge, confirm the solve.
    /// Permissionless. Returns the operator bond to the agent.
    ///
    /// A call before `ready_at_ns` aborts the receipt and leaves the record
    /// pending. The release build surfaces that abort as a wasm trap. Read
    /// `ready_at_ns` and call again after it.
    pub fn finalize(&mut self, evidence_hash: String) {
        let evidence_hash = normalize_hash("evidence hash", &evidence_hash);
        let mut record = self.take_record(&evidence_hash);
        require!(record.status == RecordStatus::Pending, "not pending");
        require!(
            env::block_timestamp() >= record.ready_at_ns,
            "challenge window open"
        );
        let agent = record.agent.clone();
        let operator_bond = record.operator_bond;
        record.status = RecordStatus::Final;
        record.operator_bond = 0;
        self.records.insert(evidence_hash.clone(), record);
        self.credit(&agent, operator_bond);
        self.bump_rep(&agent, |rep| {
            rep.pending = rep.pending.checked_sub(1).expect("pending underflow");
            rep.finalized = rep.finalized.checked_add(1).expect("finalized overflow");
        });
        emit(
            "finalize",
            serde_json::json!({
                "evidence_hash": evidence_hash,
                "agent": agent.as_str(),
            }),
        );
    }

    /// Pull yoctoNEAR credited by finalize, resolve, or expire.
    pub fn withdraw(&mut self) -> Promise {
        let account = env::predecessor_account_id();
        let amount = self.claimable.remove(&account).unwrap_or(0);
        require!(amount > 0, "nothing to withdraw");
        self.claimable_total = self
            .claimable_total
            .checked_sub(amount)
            .expect("claimable total underflow");
        Promise::new(account).transfer(NearToken::from_yoctonear(amount))
    }

    /// Owner slash. Existing counters stay so the history is still visible.
    /// `is_valid` becomes false. Bonds on open records can still be finalized
    /// or challenged; this does not trap them.
    pub fn ban_agent(&mut self, account: AccountId) {
        self.assert_owner();
        require!(self.is_registered(&account), "not registered");
        self.bump_rep(&account, |rep| {
            rep.banned = true;
        });
        emit(
            "ban_agent",
            serde_json::json!({ "agent": account.as_str() }),
        );
    }

    pub fn spec(&self) -> String {
        SPEC.to_string()
    }

    pub fn get_config(&self) -> ConfigView {
        ConfigView {
            spec: SPEC.to_string(),
            owner: self.owner.clone(),
            resolver: self.resolver.clone(),
            response_seconds: self.response_ns / SECOND_NS,
            operator_bond_yocto: self.operator_bond.to_string(),
            challenge_bond_yocto: self.challenge_bond.to_string(),
        }
    }

    pub fn get_accounting(&self) -> AccountingView {
        AccountingView {
            escrow_yocto: self.escrow.to_string(),
            claimable_total_yocto: self.claimable_total.to_string(),
        }
    }

    pub fn get_record(&self, evidence_hash: String) -> Option<RecordView> {
        let evidence_hash = normalize_hash("evidence hash", &evidence_hash);
        self.records.get(&evidence_hash).map(|record| RecordView {
            agent: record.agent.clone(),
            evidence_hash: record.evidence_hash.clone(),
            bundle_sha256: record.bundle_sha256.clone(),
            vuln_class: record.vuln_class,
            difficulty: record.difficulty,
            status: record.status.as_str().to_string(),
            ready_at_ns: record.ready_at_ns.to_string(),
            respond_by_ns: record.respond_by_ns.to_string(),
            challenger: record.challenger.clone(),
            challenge_hash: record.challenge_hash.clone(),
            operator_bond_yocto: record.operator_bond.to_string(),
            challenge_bond_yocto: record.challenge_bond.to_string(),
            passed_claim: true,
        })
    }

    pub fn get_reputation(&self, account: AccountId) -> ReputationView {
        match self.reputation.get(&account) {
            Some(rep) => ReputationView {
                account,
                registered: rep.registered,
                banned: rep.banned,
                pending: rep.pending,
                finalized: rep.finalized,
                revoked: rep.revoked,
                is_valid: rep.is_valid(),
                records: rep.records.clone(),
            },
            None => ReputationView {
                account,
                registered: false,
                banned: false,
                pending: 0,
                finalized: 0,
                revoked: 0,
                is_valid: false,
                records: Vec::new(),
            },
        }
    }

    pub fn is_valid(&self, account: AccountId) -> bool {
        self.reputation
            .get(&account)
            .map(|rep| rep.is_valid())
            .unwrap_or(false)
    }
}

impl Contract {
    fn assert_owner(&self) {
        require!(env::predecessor_account_id() == self.owner, "owner only");
    }

    fn assert_resolver(&self) {
        require!(
            env::predecessor_account_id() == self.resolver,
            "resolver only"
        );
    }

    fn is_registered(&self, account: &AccountId) -> bool {
        self.reputation
            .get(account)
            .map(|rep| rep.registered)
            .unwrap_or(false)
    }

    fn is_banned(&self, account: &AccountId) -> bool {
        self.reputation
            .get(account)
            .map(|rep| rep.banned)
            .unwrap_or(false)
    }

    fn take_record(&self, evidence_hash: &str) -> Record {
        self.records
            .get(&evidence_hash.to_string())
            .cloned()
            .unwrap_or_else(|| env::panic_str("unknown record"))
    }

    fn bump_rep(&mut self, account: &AccountId, f: impl FnOnce(&mut Reputation)) {
        let mut rep = self
            .reputation
            .get(account)
            .cloned()
            .unwrap_or_else(|| env::panic_str("not registered"));
        f(&mut rep);
        self.reputation.insert(account.clone(), rep);
    }

    fn lock(&mut self, amount: u128) {
        if amount == 0 {
            return;
        }
        self.escrow = self.escrow.checked_add(amount).expect("escrow overflow");
    }

    fn credit(&mut self, account: &AccountId, amount: u128) {
        if amount == 0 {
            return;
        }
        let current = self.claimable.get(account).copied().unwrap_or(0);
        let next = current.checked_add(amount).expect("claimable overflow");
        self.claimable.insert(account.clone(), next);
        self.claimable_total = self
            .claimable_total
            .checked_add(amount)
            .expect("claimable total overflow");
        self.escrow = self.escrow.checked_sub(amount).expect("escrow underflow");
    }
}

fn parse_yocto(raw: &str) -> u128 {
    require!(!raw.is_empty(), "bond must be a decimal yoctoNEAR string");
    require!(
        raw.bytes().all(|b| b.is_ascii_digit()),
        "bond must be a decimal yoctoNEAR string"
    );
    raw.parse::<u128>()
        .unwrap_or_else(|_| env::panic_str("bond overflow"))
}

fn normalize_hash(label: &str, raw: &str) -> String {
    let hex = raw.strip_prefix("0x").unwrap_or(raw);
    require!(hex.len() == 64, &format!("{label} must be 32-byte hex"));
    require!(
        hex.bytes().all(|b| b.is_ascii_hexdigit()),
        &format!("{label} must be 32-byte hex")
    );
    hex.to_ascii_lowercase()
}

fn emit(event: &str, data: serde_json::Value) {
    let payload = serde_json::json!({
        "standard": "axvigil-record",
        "version": "1.0.0",
        "event": event,
        "data": [data],
    });
    env::log_str(&format!("EVENT_JSON:{payload}"));
}

#[cfg(test)]
mod tests {
    use super::*;
    use near_sdk::test_utils::VMContextBuilder;
    use near_sdk::testing_env;

    const OWNER: &str = "owner.testnet";
    const AGENT: &str = "agent.testnet";
    const OTHER: &str = "other.testnet";
    const HASH_A: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const HASH_B: &str = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    const HASH_C: &str = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc";
    const BUNDLE: &str = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd";
    const COUNTER: &str = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee";

    fn ctx(predecessor: &str, deposit: u128, timestamp: u64) {
        let mut builder = VMContextBuilder::new();
        builder
            .current_account_id("axvigil.testnet".parse::<AccountId>().unwrap())
            .predecessor_account_id(predecessor.parse::<AccountId>().unwrap())
            .signer_account_id(predecessor.parse::<AccountId>().unwrap())
            .attached_deposit(NearToken::from_yoctonear(deposit))
            .account_balance(NearToken::from_near(50))
            .block_timestamp(timestamp);
        testing_env!(builder.build());
    }

    fn fresh(response_seconds: u64, operator: u128, challenge: u128) -> Contract {
        near_sdk::mock::with_mocked_blockchain(|blockchain| {
            let _ = blockchain.take_storage();
        });
        ctx(OWNER, 0, SECOND_NS);
        Contract::new(
            response_seconds,
            operator.to_string(),
            challenge.to_string(),
        )
    }

    fn register(contract: &mut Contract, account: &str) {
        ctx(account, 0, env::block_timestamp());
        contract.register_agent();
    }

    fn anchor(contract: &mut Contract, account: &str, hash: &str, window: u64, deposit: u128) {
        ctx(account, deposit, env::block_timestamp());
        contract.anchor_evidence(hash.to_string(), BUNDLE.to_string(), 0, 0, window, true);
    }

    #[test]
    fn register_and_anchor_is_pending() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        let record = contract.get_record(HASH_A.to_string()).unwrap();
        assert_eq!(record.status, "Pending");
        assert_eq!(record.agent, AGENT.parse::<AccountId>().unwrap());
        assert_eq!(record.bundle_sha256, BUNDLE);
        assert!(record.passed_claim);
        let rep = contract.get_reputation(AGENT.parse::<AccountId>().unwrap());
        assert!(rep.registered);
        assert_eq!(rep.pending, 1);
        assert_eq!(rep.records, vec![HASH_A]);
        assert!(!rep.is_valid);
        assert_eq!(contract.spec(), "axvigil-record/1");
    }

    #[test]
    #[should_panic(expected = "not registered")]
    fn anchor_requires_registration() {
        let mut contract = fresh(3600, 0, 0);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
    }

    #[test]
    #[should_panic(expected = "already registered")]
    fn double_register_rejected() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        register(&mut contract, AGENT);
    }

    #[test]
    #[should_panic(expected = "refusing a failing grade")]
    fn failing_grade_rejected() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        ctx(AGENT, 0, SECOND_NS);
        contract.anchor_evidence(HASH_A.into(), BUNDLE.into(), 0, 0, 90, false);
    }

    #[test]
    #[should_panic(expected = "evidence hash must be 32-byte hex")]
    fn bad_hash_rejected() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        ctx(AGENT, 0, SECOND_NS);
        contract.anchor_evidence("0x1234".into(), BUNDLE.into(), 0, 0, 90, true);
    }

    #[test]
    #[should_panic(expected = "invalid vulnerability class")]
    fn class_out_of_range() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        ctx(AGENT, 0, SECOND_NS);
        contract.anchor_evidence(HASH_A.into(), BUNDLE.into(), 3, 0, 90, true);
    }

    #[test]
    #[should_panic(expected = "invalid difficulty")]
    fn difficulty_out_of_range() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        ctx(AGENT, 0, SECOND_NS);
        contract.anchor_evidence(HASH_A.into(), BUNDLE.into(), 0, 9, 90, true);
    }

    #[test]
    #[should_panic(expected = "window out of range")]
    fn window_too_long() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, MAX_WINDOW_SECONDS + 1, 0);
    }

    #[test]
    #[should_panic(expected = "record exists")]
    fn duplicate_record_rejected() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        anchor(&mut contract, AGENT, &format!("0x{HASH_A}"), 90, 0);
    }

    #[test]
    fn honest_record_finalizes_after_the_window() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        let ready = contract
            .get_record(HASH_A.into())
            .unwrap()
            .ready_at_ns
            .parse::<u64>()
            .unwrap();
        ctx(OTHER, 0, ready);
        contract.finalize(HASH_A.into());
        let record = contract.get_record(HASH_A.into()).unwrap();
        assert_eq!(record.status, "Final");
        let rep = contract.get_reputation(AGENT.parse::<AccountId>().unwrap());
        assert_eq!(rep.pending, 0);
        assert_eq!(rep.finalized, 1);
        assert_eq!(rep.revoked, 0);
        assert!(rep.is_valid);
        assert!(contract.is_valid(AGENT.parse::<AccountId>().unwrap()));
        assert_eq!(contract.get_accounting().escrow_yocto, "0");
    }

    #[test]
    #[should_panic(expected = "challenge window open")]
    fn finalize_before_window_rejected() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        ctx(OTHER, 0, env::block_timestamp());
        contract.finalize(HASH_A.into());
    }

    #[test]
    fn challenge_upheld_revokes_and_leaves_an_honest_finalize() {
        let mut contract = fresh(60, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        anchor(&mut contract, AGENT, HASH_B, 90, 0);
        ctx(OTHER, 0, env::block_timestamp());
        contract.challenge(HASH_B.into(), COUNTER.into());
        assert_eq!(
            contract.get_record(HASH_B.into()).unwrap().status,
            "Challenged"
        );
        ctx(OWNER, 0, env::block_timestamp());
        contract.resolve_challenge(HASH_B.into(), true);
        assert_eq!(
            contract.get_record(HASH_B.into()).unwrap().status,
            "Revoked"
        );
        let ready = contract
            .get_record(HASH_A.into())
            .unwrap()
            .ready_at_ns
            .parse::<u64>()
            .unwrap();
        ctx(OTHER, 0, ready);
        contract.finalize(HASH_A.into());
        let rep = contract.get_reputation(AGENT.parse::<AccountId>().unwrap());
        assert_eq!(rep.finalized, 1);
        assert_eq!(rep.revoked, 1);
        assert_eq!(rep.pending, 0);
        assert!(rep.is_valid);
        assert_eq!(rep.records, vec![HASH_A, HASH_B]);
    }

    #[test]
    #[should_panic(expected = "not pending")]
    fn finalize_while_challenged_rejected() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        ctx(OTHER, 0, env::block_timestamp());
        contract.challenge(HASH_A.into(), COUNTER.into());
        let ready = contract
            .get_record(HASH_A.into())
            .unwrap()
            .ready_at_ns
            .parse::<u64>()
            .unwrap();
        ctx(OTHER, 0, ready);
        contract.finalize(HASH_A.into());
    }

    #[test]
    #[should_panic(expected = "agent cannot challenge own record")]
    fn agent_cannot_self_challenge() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        ctx(AGENT, 0, env::block_timestamp());
        contract.challenge(HASH_A.into(), COUNTER.into());
    }

    #[test]
    #[should_panic(expected = "challenge window closed")]
    fn challenge_after_window_rejected() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        let ready = contract
            .get_record(HASH_A.into())
            .unwrap()
            .ready_at_ns
            .parse::<u64>()
            .unwrap();
        ctx(OTHER, 0, ready);
        contract.challenge(HASH_A.into(), COUNTER.into());
    }

    #[test]
    fn rejected_challenge_can_still_finalize() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        ctx(OTHER, 0, env::block_timestamp());
        contract.challenge(HASH_A.into(), COUNTER.into());
        ctx(OWNER, 0, env::block_timestamp());
        contract.resolve_challenge(HASH_A.into(), false);
        assert_eq!(
            contract.get_record(HASH_A.into()).unwrap().status,
            "Pending"
        );
        let ready = contract
            .get_record(HASH_A.into())
            .unwrap()
            .ready_at_ns
            .parse::<u64>()
            .unwrap();
        ctx(OTHER, 0, ready);
        contract.finalize(HASH_A.into());
        assert_eq!(contract.get_record(HASH_A.into()).unwrap().status, "Final");
    }

    #[test]
    fn expire_returns_the_record_to_pending() {
        let mut contract = fresh(30, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        let challenged_at = env::block_timestamp();
        ctx(OTHER, 0, challenged_at);
        contract.challenge(HASH_A.into(), COUNTER.into());
        let respond_by = contract
            .get_record(HASH_A.into())
            .unwrap()
            .respond_by_ns
            .parse::<u64>()
            .unwrap();
        assert_eq!(respond_by, challenged_at + 30 * SECOND_NS);
        ctx(AGENT, 0, respond_by);
        contract.expire_challenge(HASH_A.into());
        assert_eq!(
            contract.get_record(HASH_A.into()).unwrap().status,
            "Pending"
        );
        let ready = contract
            .get_record(HASH_A.into())
            .unwrap()
            .ready_at_ns
            .parse::<u64>()
            .unwrap();
        ctx(OTHER, 0, ready);
        contract.finalize(HASH_A.into());
        assert!(contract.is_valid(AGENT.parse::<AccountId>().unwrap()));
    }

    #[test]
    #[should_panic(expected = "response window still open")]
    fn expire_before_response_rejected() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        ctx(OTHER, 0, env::block_timestamp());
        contract.challenge(HASH_A.into(), COUNTER.into());
        contract.expire_challenge(HASH_A.into());
    }

    #[test]
    #[should_panic(expected = "resolver only")]
    fn non_resolver_cannot_resolve() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        ctx(OTHER, 0, env::block_timestamp());
        contract.challenge(HASH_A.into(), COUNTER.into());
        contract.resolve_challenge(HASH_A.into(), true);
    }

    #[test]
    fn uphold_pays_the_challenger_both_bonds() {
        let mut contract = fresh(3600, 5, 7);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 5);
        assert_eq!(contract.get_accounting().escrow_yocto, "5");
        ctx(OTHER, 7, env::block_timestamp());
        contract.challenge(HASH_A.into(), COUNTER.into());
        assert_eq!(contract.get_accounting().escrow_yocto, "12");
        ctx(OWNER, 0, env::block_timestamp());
        contract.resolve_challenge(HASH_A.into(), true);
        let accounting = contract.get_accounting();
        assert_eq!(accounting.escrow_yocto, "0");
        assert_eq!(accounting.claimable_total_yocto, "12");
        ctx(OTHER, 0, env::block_timestamp());
        let _promise = contract.withdraw();
        assert_eq!(contract.get_accounting().claimable_total_yocto, "0");
        assert!(!contract.is_valid(AGENT.parse::<AccountId>().unwrap()));
        assert_eq!(
            contract
                .get_reputation(AGENT.parse::<AccountId>().unwrap())
                .revoked,
            1
        );
    }

    #[test]
    fn rejected_bond_goes_to_the_owner_and_operator_bond_returns_on_finalize() {
        let mut contract = fresh(3600, 5, 7);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 5);
        ctx(OTHER, 7, env::block_timestamp());
        contract.challenge(HASH_A.into(), COUNTER.into());
        ctx(OWNER, 0, env::block_timestamp());
        contract.resolve_challenge(HASH_A.into(), false);
        assert_eq!(contract.get_accounting().escrow_yocto, "5");
        assert_eq!(contract.get_accounting().claimable_total_yocto, "7");
        let ready = contract
            .get_record(HASH_A.into())
            .unwrap()
            .ready_at_ns
            .parse::<u64>()
            .unwrap();
        ctx(OTHER, 0, ready);
        contract.finalize(HASH_A.into());
        assert_eq!(contract.get_accounting().escrow_yocto, "0");
        assert_eq!(contract.get_accounting().claimable_total_yocto, "12");
        ctx(AGENT, 0, ready);
        let _promise = contract.withdraw();
        ctx(OWNER, 0, ready);
        let _promise = contract.withdraw();
        assert_eq!(contract.get_accounting().claimable_total_yocto, "0");
    }

    #[test]
    #[should_panic(expected = "attached deposit must equal the operator bond")]
    fn wrong_operator_deposit_rejected() {
        let mut contract = fresh(3600, 5, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 4);
    }

    #[test]
    #[should_panic(expected = "attached deposit must equal the challenge bond")]
    fn wrong_challenge_deposit_rejected() {
        let mut contract = fresh(3600, 0, 7);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        ctx(OTHER, 1, env::block_timestamp());
        contract.challenge(HASH_A.into(), COUNTER.into());
    }

    #[test]
    fn ban_clears_validity_without_erasing_counts() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        let ready = contract
            .get_record(HASH_A.into())
            .unwrap()
            .ready_at_ns
            .parse::<u64>()
            .unwrap();
        ctx(OTHER, 0, ready);
        contract.finalize(HASH_A.into());
        ctx(OWNER, 0, ready);
        contract.ban_agent(AGENT.parse::<AccountId>().unwrap());
        let rep = contract.get_reputation(AGENT.parse::<AccountId>().unwrap());
        assert!(rep.banned);
        assert_eq!(rep.finalized, 1);
        assert!(!rep.is_valid);
        assert_eq!(contract.get_record(HASH_A.into()).unwrap().status, "Final");
    }

    #[test]
    #[should_panic(expected = "agent is banned")]
    fn banned_agent_cannot_anchor() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        ctx(OWNER, 0, SECOND_NS);
        contract.ban_agent(AGENT.parse::<AccountId>().unwrap());
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
    }

    #[test]
    #[should_panic(expected = "owner only")]
    fn non_owner_cannot_ban() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        ctx(OTHER, 0, SECOND_NS);
        contract.ban_agent(AGENT.parse::<AccountId>().unwrap());
    }

    #[test]
    #[should_panic(expected = "nothing to withdraw")]
    fn withdraw_without_credit_rejected() {
        let mut contract = fresh(3600, 0, 0);
        register(&mut contract, AGENT);
        ctx(AGENT, 0, SECOND_NS);
        let _promise = contract.withdraw();
    }

    #[test]
    #[should_panic(expected = "unknown record")]
    fn unknown_record_cannot_finalize() {
        let mut contract = fresh(3600, 0, 0);
        ctx(OTHER, 0, SECOND_NS * 10);
        contract.finalize(HASH_C.into());
    }

    #[test]
    fn unknown_agent_is_not_valid() {
        let contract = fresh(3600, 0, 0);
        assert!(!contract.is_valid(AGENT.parse::<AccountId>().unwrap()));
        let rep = contract.get_reputation(AGENT.parse::<AccountId>().unwrap());
        assert!(!rep.registered);
        assert!(rep.records.is_empty());
    }

    #[test]
    #[should_panic(expected = "response window out of range")]
    fn response_window_zero_rejected() {
        fresh(0, 0, 0);
    }

    #[test]
    fn owner_can_point_the_resolver_at_another_account() {
        let mut contract = fresh(3600, 0, 0);
        ctx(OWNER, 0, SECOND_NS);
        contract.set_resolver(OTHER.parse::<AccountId>().unwrap());
        assert_eq!(
            contract.get_config().resolver,
            OTHER.parse::<AccountId>().unwrap()
        );
        register(&mut contract, AGENT);
        anchor(&mut contract, AGENT, HASH_A, 90, 0);
        ctx(OTHER, 0, env::block_timestamp());
        contract.challenge(HASH_A.into(), COUNTER.into());
        contract.resolve_challenge(HASH_A.into(), true);
        assert_eq!(
            contract.get_record(HASH_A.into()).unwrap().status,
            "Revoked"
        );
    }
}
