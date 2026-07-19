# Security

Report vulnerabilities privately to clint@2389.ai; expect an
acknowledgement within a week. Do not open public issues for
exploitable defects.

Relevant guarantees the press intends to keep (breakage of any is a
vulnerability): source archives never dereference symlinks and refuse
secret-prone files; every generated output stays beneath the book
root under a validated slug; CI outputs cannot be injected through
book metadata; published sites carry only local, resolving
references; three-part release tags are immutable across pipeline,
action, and toolchain.
