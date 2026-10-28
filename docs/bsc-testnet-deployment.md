# BSC testnet deployment checklist

This checklist is for the AxVigil hackathon deployment only. Use a wallet created specifically for BSC testnet. Never use a wallet that holds mainnet assets.

## Prepare the wallet

1. Create a fresh testnet-only wallet.
2. Add BSC Testnet with chain ID `97`, currency `tBNB`, RPC `https://data-seed-prebsc-1-s1.bnbchain.org:8545` and explorer `https://testnet.bscscan.com/`.
3. Request tBNB from the [official BNB Chain testnet faucet](https://www.bnbchain.org/en/testnet-faucet).
4. Keep the private key local. Do not commit `.env` or paste the key into chat.

## Run preflight

From the repository root:

```bash
export BSC_TESTNET_RPC=https://data-seed-prebsc-1-s1.bnbchain.org:8545
export PRIVATE_KEY=0x...
export SIGNER=0x...  # optional; defaults to the deployer address
./scripts/bsc_preflight.sh
```

The script checks chain ID `97`, derives the deployer address locally, checks its tBNB balance and prints the explorer link. It refuses to continue if the network is not BSC testnet or the balance is below `MIN_TBNB` (default `0.01`). It never prints the private key.

## Deploy only after preflight

```bash
cd contracts
source .env
forge script script/Deploy.s.sol \
  --rpc-url "$BSC_TESTNET_RPC" \
  --broadcast
```

The deployment script refuses chains other than 97. Record the addresses and transaction hashes from its output. Verify source code on [BscScan Testnet's contract verification page](https://testnet.bscscan.com/verifyContract) only after confirming the deployed addresses.

## Post-deployment checks

- Check `AxVigilSkill`, `AxVigilCollectible` and registry addresses on BscScan Testnet.
- Confirm `AxVigilCollectible.signer()` matches the intended MintAuth signer.
- Confirm `AxVigilCollectible.currentBatch()` is non-zero if minting is expected immediately.
- Confirm the collectible has the intended owner and hourly cap.
- Test one complete verifier → signature → mint flow with a disposable Agent ID.
- Do not use the demo `MockAgentID` as a production registry; it is open-mint and testnet/demo-only.
