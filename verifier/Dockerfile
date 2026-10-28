FROM ghcr.io/foundry-rs/foundry:v1.7.1 AS foundry
FROM python:3.12-slim
COPY --from=foundry /usr/local/bin/forge /usr/local/bin/forge
COPY --from=foundry /usr/local/bin/anvil /usr/local/bin/anvil
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Fetch compiler at build time; the runtime container has no network.
RUN mkdir -p /tmp/warm/src && printf 'pragma solidity ^0.8.28; contract Warm {}' > /tmp/warm/src/Warm.sol \
    && cd /tmp/warm && forge build --use 0.8.28 \
    && mkdir -p /opt/solc && cp /root/.svm/0.8.28/solc-0.8.28 /opt/solc/solc-0.8.28 \
    && rm -rf /tmp/warm
COPY challenges challenges
COPY verifier verifier
ENV HOME=/tmp PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 FOUNDRY_SOLC=/opt/solc/solc-0.8.28
USER 65532:65532
ENTRYPOINT ["python", "-m", "verifier.worker"]
