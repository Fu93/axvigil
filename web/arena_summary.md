# AxVigil arena

Powered by Meta Muse Spark.

Same rendered challenges for every contestant. The AxVigil verifier grades
each patch and proof of concept. Ranked by pass rate, then fewer attempts,
then fewer tokens. Only completed runs count.

Requests this process: 74 / 80.

## Ranking

| Rank | Contestant | Strategy | Pass rate | Passes | Runs | Attempts | Prompt tokens | Completion tokens |
|---|---|---|---|---|---|---|---|---|
| 1 | muse-spark-1.2 | baseline | 100% | 6 | 6 | 7 | 7931 | 56166 |
| 2 | muse-spark-1.1 | baseline | 100% | 6 | 6 | 8 | 9560 | 61229 |
| 3 | muse-spark-1.3 | baseline | 100% | 6 | 6 | 8 | 10205 | 68755 |
| 4 | muse-spark-1.2:agentic | agentic | 83% | 5 | 6 | 6 | 182804 | 54611 |
| 5 | muse-spark-1.2:plan-then-patch | plan-then-patch | 83% | 5 | 6 | 9 | 26352 | 98965 |
| 6 | muse-spark-1.1:agentic | agentic | 50% | 3 | 6 | 6 | 187327 | 32625 |

## Per mother

| Contestant | reentrancy | price-manipulation | access-control | signature-replay | bridge-phantom-deposit | empty-market-inflation |
|---|---|---|---|---|---|---|
| muse-spark-1.2 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| muse-spark-1.1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| muse-spark-1.3 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| muse-spark-1.2:agentic | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 0/1 |
| muse-spark-1.2:plan-then-patch | 1/1 | 1/1 | 1/1 | 1/1 | 0/1 | 1/1 |
| muse-spark-1.1:agentic | 1/1 | 1/1 | 1/1 | 0/1 | 0/1 | 0/1 |

## Runs

| Contestant | Mother | Seed | Status | Pass | Attempts | Requests | Tokens | Latency ms | Checks | Diff lines |
|---|---|---|---|---|---|---|---|---|---|---|
| muse-spark-1.1 | reentrancy | 1 | completed | True | 2 | 2 | 14859 | 53684 | pocProvesBug=no pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.1 | price-manipulation | 1 | completed | True | 1 | 1 | 5553 | 20010 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.1 | access-control | 1 | completed | True | 1 | 1 | 4510 | 17897 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 1 |
| muse-spark-1.1 | signature-replay | 1 | completed | True | 1 | 1 | 6001 | 22306 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.1 | bridge-phantom-deposit | 1 | completed | True | 2 | 2 | 29280 | 92056 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=no patchWithinLimits=yes || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 6 |
| muse-spark-1.1 | empty-market-inflation | 1 | completed | True | 1 | 1 | 10586 | 31820 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 4 |
| muse-spark-1.2 | reentrancy | 1 | completed | True | 1 | 1 | 6172 | 25837 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 4 |
| muse-spark-1.2 | price-manipulation | 1 | completed | True | 1 | 1 | 5155 | 20096 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.2 | access-control | 1 | completed | True | 1 | 1 | 4457 | 19606 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 1 |
| muse-spark-1.2 | signature-replay | 1 | completed | True | 1 | 1 | 4147 | 19122 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.2 | bridge-phantom-deposit | 1 | completed | True | 2 | 2 | 34836 | 105097 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=no patchWithinLimits=yes || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.2 | empty-market-inflation | 1 | completed | True | 1 | 1 | 9330 | 32364 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 5 |
| muse-spark-1.3 | reentrancy | 1 | completed | True | 1 | 1 | 5751 | 66494 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.3 | price-manipulation | 1 | completed | True | 1 | 1 | 4688 | 33931 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.3 | access-control | 1 | completed | True | 1 | 1 | 3683 | 41876 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 1 |
| muse-spark-1.3 | signature-replay | 1 | completed | True | 1 | 1 | 4215 | 33752 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.3 | bridge-phantom-deposit | 1 | completed | True | 2 | 2 | 30140 | 315219 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=no patchWithinLimits=yes || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.3 | empty-market-inflation | 1 | completed | True | 2 | 2 | 30483 | 209640 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 4 |
| muse-spark-1.1:agentic | reentrancy | 1 | completed | True | 1 | 10 | 33739 | 37312 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 6 |
| muse-spark-1.1:agentic | price-manipulation | 1 | completed | True | 1 | 10 | 36686 | 42873 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.1:agentic | access-control | 1 | completed | True | 1 | 10 | 30713 | 32835 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 1 |
| muse-spark-1.1:agentic | signature-replay | 1 | completed | False | 1 | 10 | 35287 | 25260 | no patch submitted | 0 |
| muse-spark-1.1:agentic | bridge-phantom-deposit | 1 | completed | False | 1 | 10 | 41260 | 34583 | no patch submitted | 0 |
| muse-spark-1.1:agentic | empty-market-inflation | 1 | completed | False | 1 | 10 | 42267 | 46036 | no patch submitted | 0 |
| muse-spark-1.2:plan-then-patch | reentrancy | 1 | completed | True | 1 | 2 | 9617 | 35908 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.2:plan-then-patch | price-manipulation | 1 | completed | True | 2 | 4 | 20699 | 59207 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=no || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.2:plan-then-patch | access-control | 1 | completed | True | 1 | 2 | 5408 | 22209 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 1 |
| muse-spark-1.2:plan-then-patch | signature-replay | 1 | completed | True | 1 | 2 | 7269 | 26742 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.2:plan-then-patch | bridge-phantom-deposit | 1 | completed | False | 3 | 6 | 67708 | 176227 | pocProvesBug=no pocFailsAfterPatch=yes hiddenTestsPass=no patchWithinLimits=yes || pocProvesBug=no pocFailsAfterPatch=yes hiddenTestsPass=no patchWithinLimits=yes || pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=no patchWithinLimits=yes | 1 |
| muse-spark-1.2:plan-then-patch | empty-market-inflation | 1 | completed | True | 1 | 2 | 14616 | 43258 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 6 |
| muse-spark-1.2:agentic | reentrancy | 1 | completed | True | 1 | 8 | 28957 | 35419 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 6 |
| muse-spark-1.2:agentic | price-manipulation | 1 | completed | True | 1 | 9 | 33948 | 49338 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.2:agentic | access-control | 1 | completed | True | 1 | 8 | 25351 | 34580 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 1 |
| muse-spark-1.2:agentic | signature-replay | 1 | completed | True | 1 | 8 | 27937 | 39882 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 3 |
| muse-spark-1.2:agentic | bridge-phantom-deposit | 1 | completed | True | 1 | 12 | 58441 | 69519 | pocProvesBug=yes pocFailsAfterPatch=yes hiddenTestsPass=yes patchWithinLimits=yes | 2 |
| muse-spark-1.2:agentic | empty-market-inflation | 1 | completed | False | 1 | 11 | 62781 | 82587 | no patch submitted | 0 |
