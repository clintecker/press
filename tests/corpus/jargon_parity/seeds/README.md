# Differential seeds

This directory holds minimized inputs that once made the two jargon
checkers disagree. The property-based differential test in
`tests/test_jargon_parity.py` writes a seed here (and fails) whenever it
generates text the package copy and the portable skill copy score
differently; the seed then becomes a permanent regression case replayed
on every run.

It is empty because the two implementations currently agree on every
input the fuzzer has explored. A file appearing here is a caught drift,
not noise: fix the divergence, keep the seed.
