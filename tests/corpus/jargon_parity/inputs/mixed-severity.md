# Mixed severity

The seam between the two services is load-bearing, and the blast radius is
wide. We watched the drift and measured the parity before we shipped.

That paragraph mixes rewrite terms (seam, load-bearing, blast radius) with
inspect terms (drift, parity, shipped), so both checkers must agree on the
count, the per-term status, and the exit code at every --fail-on threshold.
