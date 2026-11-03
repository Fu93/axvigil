# Grading sandbox. Foundry is pinned to the release this repo's tests used.
# Build: docker build -t axvigil-sandbox:1.8.7 verifier/docker
# solc 0.8.28 is fetched at image build time. Runtime uses --network none.
FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

ARG FOUNDRY_VERSION=1.8.7
RUN curl -fsSL -o /tmp/foundry.tgz \
      "https://github.com/foundry-rs/foundry/releases/download/v${FOUNDRY_VERSION}/foundry_v${FOUNDRY_VERSION}_linux_amd64.tar.gz" \
    && tar -xzf /tmp/foundry.tgz -C /usr/local/bin forge \
    && rm /tmp/foundry.tgz \
    && forge --version

# Download solc while the build still has a network, into the runtime user's home.
# Ubuntu 24.04 already ships a uid-1000 user. Reuse that numeric uid for the
# sandbox identity; the runtime still passes --user 1000:1000 and never runs as root.
RUN useradd --uid 1000 --non-unique --create-home --shell /usr/sbin/nologin axvigil \
    && mkdir -p /tmp/warmup/src \
    && printf 'pragma solidity 0.8.28;\ncontract W { function f() external pure returns (uint256) { return 1; } }\n' > /tmp/warmup/src/W.sol \
    && printf '[profile.default]\nsrc="src"\nout="out"\nsolc_version="0.8.28"\n' > /tmp/warmup/foundry.toml \
    && chown -R axvigil:axvigil /tmp/warmup
# Set this before the warmup build; otherwise the base image's HOME causes the
# compiler cache to be downloaded into a different user's directory.
ENV HOME=/home/axvigil \
    FOUNDRY_HOME=/home/axvigil/.foundry
USER axvigil
RUN cd /tmp/warmup && forge build
USER root
# Keep the runtime user's home identical to the build-time home so the warmed
# offline solc cache is available when Docker invokes the container by numeric
# uid (which has no passwd-entry home resolution).
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh
USER axvigil
ENTRYPOINT ["/entrypoint.sh"]
