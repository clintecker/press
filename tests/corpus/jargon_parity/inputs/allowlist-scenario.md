# Allowlist scenario

We measured the drift and confirmed parity, then noted the seam between the
services. The drift and parity terms are silenced per-run by --allow, while
seam stays a finding, so the allowlist behaviour must be identical in both
checkers whether a term is allowed once, twice, or by a different case.
