# Regex and phrase ordering

The big data pipeline logged the data, and a co-occurrence table plus a
plain cooccurrence count fell out of the run. The word "the" is on the
allow list, so it never becomes a finding.

This input is scanned with watchlists/ok-regex.csv to exercise the regex
match path, the phrase-before-word ordering, and the allow-status skip in
both checkers at once.
