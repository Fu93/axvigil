# AxVigil arena

**Run metadata.** 2026-11-02 22:14 GMT, commit `2c45b7a`, 83/114 requests, 412,196 tokens, 865 s. The tables below are the recorded run and were not regenerated.

Powered by Meta Muse Spark.

Same rendered challenges for every contestant. The AxVigil verifier grades
each patch and proof of concept. Ranked by pass rate, then fewer attempts,
then fewer tokens. Only completed runs count.

Requests this process: 83 / 114.

## Ranking

| Rank | Contestant | Strategy | Pass rate | Passes | Runs | Attempts | Prompt tokens | Completion tokens |
|---|---|---|---|---|---|---|---|---|
| 1 | muse-spark-1.1 | baseline | 100% | 6 | 6 | 7 | 7860 | 44640 |
| 2 | muse-spark-1.2 | baseline | 100% | 6 | 6 | 8 | 9541 | 51479 |
| 3 | muse-spark-1.3 | baseline | 100% | 6 | 6 | 9 | 11976 | 67099 |
| 4 | muse-spark-1.1:agentic | agentic | 67% | 4 | 6 | 5 | 179146 | 40455 |

## Per mother

| Contestant | reentrancy | price-manipulation | access-control | signature-replay | bridge-phantom-deposit | empty-market-inflation |
|---|---|---|---|---|---|---|
| muse-spark-1.1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| muse-spark-1.2 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| muse-spark-1.3 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| muse-spark-1.1:agentic | 1/1 | 1/1 | 1/1 | 1/1 | 0/1 | 0/1 |

## Runs

| Contestant | Mother | Seed | Status | Pass | Attempts | Requests | Tokens | Latency ms | Checks | Diff lines |
|---|---|---|---|---|---|---|---|---|---|---|
| muse-spark-1.1 | reentrancy | 1 | completed | True | 1 | 1 | 6777 | 25295 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.1 | price-manipulation | 1 | completed | True | 1 | 1 | 4773 | 15140 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.1 | access-control | 1 | completed | True | 1 | 1 | 4400 | 13440 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 1 |
| muse-spark-1.1 | signature-replay | 1 | completed | True | 1 | 1 | 5368 | 15784 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.1 | bridge-phantom-deposit | 1 | completed | True | 2 | 2 | 17334 | 43058 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=no patchWithinLimits=yes || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.1 | empty-market-inflation | 1 | completed | True | 1 | 1 | 13848 | 32456 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.2 | reentrancy | 1 | completed | True | 2 | 2 | 12699 | 56381 | pocProvesBug=no pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.2 | price-manipulation | 1 | completed | True | 1 | 1 | 4586 | 12268 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.2 | access-control | 1 | completed | True | 1 | 1 | 4941 | 20346 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 1 |
| muse-spark-1.2 | signature-replay | 1 | completed | True | 1 | 1 | 6886 | 21254 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.2 | bridge-phantom-deposit | 1 | completed | True | 2 | 2 | 21478 | 63957 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=no patchWithinLimits=yes || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.2 | empty-market-inflation | 1 | completed | True | 1 | 1 | 10430 | 36278 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 4 |
| muse-spark-1.3 | reentrancy | 1 | completed | True | 1 | 1 | 4846 | 23887 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.3 | price-manipulation | 1 | completed | True | 1 | 1 | 4983 | 22546 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.3 | access-control | 1 | completed | True | 1 | 1 | 3344 | 17578 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 1 |
| muse-spark-1.3 | signature-replay | 1 | completed | True | 2 | 2 | 9886 | 42760 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=no || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.3 | bridge-phantom-deposit | 1 | completed | True | 3 | 3 | 43951 | 162816 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=no patchWithinLimits=yes || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=no patchWithinLimits=yes || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 4 |
| muse-spark-1.3 | empty-market-inflation | 1 | completed | True | 1 | 1 | 12065 | 48443 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 4 |
| muse-spark-1.1:agentic | reentrancy | 1 | completed | True | 1 | 10 | 33364 | 29766 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 6 |
| muse-spark-1.1:agentic | price-manipulation | 1 | completed | True | 1 | 10 | 38395 | 25755 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.1:agentic | access-control | 1 | completed | True | 1 | 10 | 30052 | 22866 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 1 |
| muse-spark-1.1:agentic | signature-replay | 1 | completed | True | 1 | 10 | 32887 | 26498 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.1:agentic | bridge-phantom-deposit | 1 | completed | False | 1 | 9 | 40367 | 44842 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=no patchWithinLimits=yes | 1 |
| muse-spark-1.1:agentic | empty-market-inflation | 1 | completed | False | 0 | 10 | 44536 | 40928 | — | 0 |
