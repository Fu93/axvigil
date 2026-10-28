// UI regression test with mocked wallet/API. Actual chain integration lives in test_api.py.
const { spawn } = require("node:child_process");
const server = spawn(
  process.env.PYTHON || "python3",
  ["-m", "http.server", "8765", "--bind", "127.0.0.1", "--directory", "web"],
  { stdio: "ignore" },
);
process.on("exit", () => server.kill());
const { chromium } = require("playwright");
(async () => {
  for (let i = 0; i < 50; i++) {
    try {
      await fetch("http://127.0.0.1:8765");
      break;
    } catch {
      await new Promise((r) => setTimeout(r, 100));
    }
  }
  const b = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE }
      : {}),
  });
  const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  let state = "issued";
  let mint = false;
  await p.addInitScript(() => {
    window.ethereum = {
      on() {},
      async request(r) {
        if (r.method === "eth_requestAccounts") return ["0x" + "1".repeat(40)];
        if (r.method === "eth_chainId") return "0x7a69";
        if (r.method === "eth_signTypedData_v4") return "0xsignature";
        if (r.method === "eth_sendTransaction") return "0xtransaction";
        if (r.method === "eth_getTransactionReceipt") return { status: "0x1" };
        throw Error(r.method);
      },
    };
  });
  await p.route("**/api/**", async (r) => {
    const path = new URL(r.request().url()).pathname;
    let data;
    if (path.endsWith("protocol_info"))
      data = {
        chainId: 31337,
        minted: 0,
        maxSupply: 7777,
        open: true,
        collectible: "0x" + "2".repeat(40),
      };
    else if (path.endsWith("prepare"))
      data = { nonce: "nonce", typedData: { message: { agentId: "1" } } };
    else if (path.endsWith("login")) data = { token: "token" };
    else if (path.includes("/skills/"))
      data = {
        record: {
          exists: mint,
          totalSolves: mint ? 1 : 0,
          solvesPerClass: [1, 0, 0],
        },
        collectiblesMinted: mint ? 1 : 0,
      };
    else if (path.endsWith("start")) data = { challengeId: "ax-test" };
    else if (path.includes("/fragments/"))
      data = { code: "contract Challenge {}", title: "Test", total: 1 };
    else if (path.endsWith("submit")) {
      state = "passed";
      data = { state: "grading" };
    } else if (path.endsWith("status"))
      data = {
        state,
        result:
          state === "passed"
            ? {
                pocProvesBug: true,
                pocFailsAfterPatch: true,
                hiddenTestsPass: true,
                patchWithinLimits: true,
              }
            : null,
      };
    else if (path.endsWith("authorize")) {
      mint = true;
      data = { calldata: "0xcalldata" };
    } else throw Error(path);
    await r.fulfill({ json: data });
  });
  await p.goto("http://127.0.0.1:8765");
  if (await p.evaluate(() => document.documentElement.scrollWidth > innerWidth))
    throw Error("Mobile page overflows");
  await p.setViewportSize({ width: 1440, height: 1100 });
  if (await p.evaluate(() => document.documentElement.scrollWidth > innerWidth))
    throw Error("Desktop page overflows");
  await p.setViewportSize({ width: 390, height: 844 });
  await p.locator("#agentId").fill("1");
  await p.locator("#connect").click();
  await p.locator("#start").click();
  await p.locator("#poc").fill("contract Attack {}");
  await p.locator("#submit").click();
  await p.waitForFunction(() => !document.querySelector("#mint").disabled);
  if (!(await p.locator("#submit").isDisabled()))
    throw Error("Submit enabled after final grade");
  await p.locator("#mint").click();
  await p.waitForFunction(() =>
    document.querySelector("#message").textContent.startsWith("Mint confirmed"),
  );
  if (!(await p.locator("#mint").isDisabled()))
    throw Error("Mint button remained enabled");
  console.log({
    flow: await p.locator("#message").innerText(),
    overflow: await p.evaluate(
      () => document.documentElement.scrollWidth > innerWidth,
    ),
    skill: await p.locator("#skillRecord").innerText(),
  });
  await b.close();
  server.kill();
})().catch((e) => {
  console.error(e);
  server.kill();
  process.exit(1);
});
