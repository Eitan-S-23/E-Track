# P51 New-Source Candidate Preparation

Independent candidate-artifact review PASS, not a P5 hardware acceptance bundle.
Actual source: `1430c8ff7f3bcd9a35bfe158ba697b99021f75f2` on
`dev/firmware/p51-packaging-20261104`; later evidence commits do not change that
build identity or its timestamp 1793820855.

Run `41900439548/1`, artifact `13359301400`, 6586031 bytes, SHA-256
`a906221d772a0df5b6b069a250a5b8f951b97371bacd1a8be4b0d77c51988e0b`.
`artifact.zip` and `workflow-logs.zip` are exact GitHub originals.
`provenance.zip` retains the root scripts, local review, actual-next-timestamp
prediction, remote intents/readbacks and process receipts, with its own index.
`index.json` binds this directory; `review.json` is the independent seven-check
original-artifact evaluation. No private header/key was downloaded or exported.

One real GCC source compilation, three fw_header finalizations: FULL-cell start
3.3.17, exact PATCH base 3.3.18, target 3.3.19. Each App is 615132 bytes and includes
the independently reviewed UI repairs. Finalized identities:

| Asset | SHA-256 |
| --- | --- |
| Full-cell start | `0fc735659ad2febf7eed7bd2576bfc2a0605f706b3924bffd7ea0b24099a82b9` |
| Patch base | `74c20ab69baa85e73cd6273d84dea95e53428fd81620d184d25c859d150407a1` |
| Target | `fdd065a8871bcffcc8e262fa4a43a71cbf20752adab9904a27c0eb59d8f7b89d` |
| Full, 291700 bytes | `fd3f610f1c0a918e152c61b604e4d1646adc551a1b33c21e8a04adce9eb19140` |
| Patch/reference, 1048576 bytes | `919036dc304dfafc236bf593bca1c1da29a816067b67eb74b14d77a7d100dfee` |
| Recovery, 615140 bytes | `f3d7951c077b402c275d83d0bc24c381be5c8fb65068e6242279c1d231b61336` |

The external approved group16 Boot is 14800 bytes, SHA-256
`2f84014278421de7a84a0f621a494a9974fbf51c56b768974b0c5e647105ec80`.
The ordinary Boot compiled in this run remains compile-only, not the selected
Boot. Do not confuse a binary's digest with a padded full-flash-region digest.

The actual CI raw GCC App exactly matches the retained raw image used by root's
new-commit prediction. Both use v4 with 140 unique encodings, count 210428,
seed 7, salt 24. The compressed stream is 1048472 bytes and strictly reconstructs
the target without trailing bytes or padding. Linux sampled-encoding time sums
to 226.0572 seconds; this is not whole-job or whole-package wall time. The local
cold prediction took 527.130 seconds including strict verification.

CI host checks: Node 50, Python 19, all pass. Actual native originals include
12 checks and 16 closed process receipts; zero native warnings/errors. GCC build
has 641 warnings and zero errors. Size output: App text/data/bss
612760/940/558664; ordinary compile-only Boot 14720/4/9780.

One user-delegated protected approval, no policy edits; repository/rehearsal/
production gates remain false. Post-CI service channels/releases match pre-CI.
Old candidate assets and failed searches/runs remain unchanged. No device, SD,
service publication, 30/30, soak, four-combination verdict or P5 freeze occurred.
Next preparation must bind the two actual backup/restore identities and the
selected App/APK/ELF/MAP before any installation or physical test.
