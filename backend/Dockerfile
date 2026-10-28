# AxVigil platform API — FastAPI + the forge/solc toolchain the grader shells out to.
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PATH="/root/.foundry/bin:${PATH}" \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl git ca-certificates && rm -rf /var/lib/apt/lists/*

# Foundry (forge, cast, anvil)
RUN curl -L https://foundry.paradigm.xyz | bash && foundryup

WORKDIR /app
COPY . /app

# Python deps
RUN pip install --no-cache-dir -r backend/requirements.txt

# Fetch libs and warm the solc cache so offline grading can compile with no network.
RUN git submodule update --init --recursive || true
RUN cd contracts && forge build

EXPOSE 8000
# SIGNER_KEY, VERIFYING_CONTRACT, SESSION_SECRET, etc. come from the environment.
CMD ["uvicorn", "axvigil_backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "backend"]
