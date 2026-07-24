// Sweep the open issue board, implement the selected issues in isolated worktree
// branches, review each adversarially, repair, and report the branches for a
// human-sequenced merge. Reusable: invoke with Workflow({ name:
// "sweep-and-implement" }) or Workflow({ scriptPath: ".claude/workflows/
// sweep-and-implement.js", args: { max: 5, only: [201, 202] } }).
//
// Hardened from the first run's failures:
//  - agents claimed commits that never landed  -> they return the commit SHA,
//    and review's first act is to confirm the branch actually has commits.
//  - the dev venv's editable install points at main, so the pre-commit hook
//    tested the wrong code and silently rejected the commit -> the implement
//    prompt tells agents to test with PYTHONPATH=src and commit --no-verify
//    after a manual pass, always leaving a real commit on the branch.
//  - a strict schema hit the retry cap -> schemas are lenient (few required
//    fields, additionalProperties true).
export const meta = {
  name: 'sweep-and-implement',
  description: 'Sweep the open issue board, implement selected issues in worktree branches, review each, repair, and report branches for a sequenced merge',
  phases: [
    { title: 'Sweep', detail: 'triage the open board into a conservative work-list' },
    { title: 'Implement', detail: 'one agent per work-unit in its own worktree branch' },
    { title: 'Review', detail: 'adversarial review of each branch against its issue(s)' },
    { title: 'Repair', detail: 'fix the review findings in the branch' },
  ],
}

const TRAILER = 'Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_013syr4TLhFwQC95ksBRKTH9'
const WT = (slug) => '$HOME/code/press-worktrees/' + slug
const MAX = (args && args.max) || 5
const ONLY = (args && args.only) || null

const WORKLIST_SCHEMA = {
  type: 'object',
  properties: {
    units: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          slug: { type: 'string' },
          issues: { type: 'array', items: { type: 'number' } },
          title: { type: 'string' },
          scope: { type: 'string' },
          rationale: { type: 'string' },
        },
        required: ['slug', 'issues', 'scope'],
      },
    },
    excluded: { type: 'array', items: { type: 'string' } },
    note: { type: 'string' },
  },
  required: ['units'],
  additionalProperties: true,
}
const IMPL_SCHEMA = {
  type: 'object',
  properties: {
    branch: { type: 'string' },
    commitSha: { type: 'string' },
    committed: { type: 'boolean' },
    summary: { type: 'string' },
    filesChanged: { type: 'array', items: { type: 'string' } },
    checksRun: { type: 'string' },
    checksPassed: { type: 'boolean' },
    alreadyDone: { type: 'boolean' },
    notes: { type: 'string' },
  },
  required: ['summary', 'committed'],
  additionalProperties: true,
}
const REVIEW_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['pass', 'needs-work'] },
    branchHasCommits: { type: 'boolean' },
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: { severity: { type: 'string' }, file: { type: 'string' }, problem: { type: 'string' }, fix: { type: 'string' } },
        required: ['problem'],
      },
    },
    summary: { type: 'string' },
  },
  required: ['verdict', 'summary'],
  additionalProperties: true,
}
const REPAIR_SCHEMA = {
  type: 'object',
  properties: {
    fixed: { type: 'array', items: { type: 'string' } },
    unresolved: { type: 'array', items: { type: 'string' } },
    committed: { type: 'boolean' },
    summary: { type: 'string' },
  },
  required: ['summary'],
  additionalProperties: true,
}

// ---- SWEEP: triage the board into a conservative work-list ------------------
phase('Sweep')
const sweep = await agent(
`Sweep the open GitHub issue board of clintecker/press and select a conservative work-list an autonomous agent can safely implement. You have gh. Do NOT change anything -- return a plan.

## Gather
- \`gh issue list --state open --limit 100 --json number,title,labels,milestone,body\`.
- For any issue you'd select, read it fully: \`gh issue view N\`. Cross-check against CHANGELOG.md and recent \`git log\` to catch already-shipped work.

## Select ONLY issues that are all of:
- **Implementable in code/docs/tests** by one agent in a few hours, well-bounded.
- **Not already shipped** (verify against the CHANGELOG / code -- say VERIFY and check, never assume).
- **Not blocked on a human or external** (exclude #87 second-party proofs and #143 golden-copy order).
- **Not the deferred block** (exclude milestone "Custom MoR (deferred)").
- **Not primarily repo-settings/admin** (exclude issues whose substance is GitHub rulesets/toggles rather than code, e.g. #153/#154).
- **Not too architectural for autonomous work** (exclude a large extension/registration mechanism like #173 unless it has a genuinely bounded slice).
- **Not needing a product/taste decision** you shouldn't make autonomously.

Prefer P1 over P2 over P3. Group two issues into ONE unit only if they are the same change; otherwise one issue per unit. Cap at ${MAX} units.${ONLY ? ` The operator restricted this run to these issues ONLY: ${JSON.stringify(ONLY)} -- select from those and ignore the rest.` : ''}

## Return
units: [{ slug: "issue-<n>", issues: [<n>], title, scope (2-4 sentences an implementer can act on, including the failing case and the house-law wiring needed), rationale }]. Also return \`excluded\`: short "#N: reason" lines for the notable issues you did NOT pick, and a \`note\`. If nothing qualifies, return units: [].`,
  { label: 'sweep', phase: 'Sweep', agentType: 'general-purpose', schema: WORKLIST_SCHEMA },
)

const units = ((sweep && sweep.units) || []).slice(0, MAX)
log(`sweep selected ${units.length} unit(s): ${units.map((u) => '#' + (u.issues || []).join('+')).join(', ') || 'none'}`)
if (sweep && sweep.excluded && sweep.excluded.length) log(`excluded: ${sweep.excluded.slice(0, 8).join(' | ')}`)
if (!units.length) {
  return { units: [], note: (sweep && sweep.note) || 'sweep selected no actionable issues' }
}

// ---- IMPLEMENT -> REVIEW -> REPAIR, per unit, independently ----------------
const results = await pipeline(
  units,

  (u) => agent(
`Implement GitHub issue(s) ${u.issues.map((n) => '#' + n).join(', ')} on clintecker/press in an ISOLATED git worktree so it can be reviewed and merged on its own.

## Setup FIRST
- Read each issue: \`gh issue view <n>\`. Read CLAUDE.md and CONTRIBUTING.md for the house laws.
- \`git worktree add -b ${u.slug} "${WT(u.slug)}" main\` (reuse if it exists; retry on a lock error). \`cd "${WT(u.slug)}"\`. Do ALL work there; never touch ~/code/press or another worktree.

## Task
${u.scope}

## House laws (must follow)
- A checker/validator is only real with a known-bad fixture it REJECTS. Assert behavior/artifacts, not "it ran". Write a test that fails before and passes after.
- A new CLI target/config key/doc lands in the SAME commit as its docs: \`python3 -m press selftest --write-docs\` regenerates docs/REFERENCE.md; name a new target in README.md; classify new public callables in quality/surfaces.yaml; add a coverage floor in quality/coverage-baseline.json (measure branch cov, floor just under; NEVER coverage_ratchet.py --update on macOS).
- Route boundaries (network, env, subprocess) through press.adapters. Keep ruff complexity <= 15, no noqa. Match surrounding style.

## CRITICAL -- committing in a worktree (the gotcha that broke the last run)
The dev venv's editable install points at ~/code/press/src (MAIN), so the pre-commit hook's pytest runs against MAIN's code, not your branch -- your new tests will FAIL the hook even when they are correct. So:
1. Run your targeted tests with \`PYTHONPATH=src python3 -m pytest ...\` (and ruff/mypy) IN the worktree; make them green against the BRANCH code.
2. Commit to the ${u.slug} branch. If the hook rejects the commit only because it tested main's code, commit again with \`--no-verify\` (you have already verified manually). NEVER leave work merely staged.
3. Confirm the commit exists: \`git log --oneline main..HEAD\` must show it. Do NOT push. End the message with:
${TRAILER}

Return your branch, the commitSha (\`git rev-parse HEAD\`), whether you committed, a summary, filesChanged, which checks you ran and whether they passed, and whether the issue was already done.`,
    { label: `impl:${u.slug}`, phase: 'Implement', agentType: 'general-purpose', schema: IMPL_SCHEMA },
  ).then((impl) => ({ u, impl })),

  (x) => {
    if (!x || !x.impl) return null
    return agent(
`Adversarially review issue(s) ${x.u.issues.map((n) => '#' + n).join(', ')} on branch \`${x.u.slug}\` (worktree "${WT(x.u.slug)}") BEFORE it merges. Be skeptical.

## FIRST: is there anything to review?
Run \`git -C ~/code/press log --oneline main..${x.u.slug}\`. If it shows NO commits, the work was never committed (the last run's failure mode) -- return verdict "needs-work", branchHasCommits false, and a single finding "work not committed to the branch". Otherwise set branchHasCommits true and continue.

## Read
- The issue(s): \`gh issue view <n>\` -- acceptance criteria + invariants are the bar.
- The diff: \`git -C ~/code/press diff main...${x.u.slug}\` and the changed files.
- The implementer's summary: ${JSON.stringify(x.impl).slice(0, 1200)}

## Judge (all of these)
- Does it satisfy EVERY acceptance criterion, not just the easy one? Does the fix work for the failing case? Edge cases?
- House laws: a new checker has a known-bad it rejects? New target/config/docs wired (REFERENCE, README, surfaces, coverage)? Boundaries via adapters? Complexity? Tests that fail-before/pass-after?
- Run \`cd "${WT(x.u.slug)}" && PYTHONPATH=src scripts/verify.sh --quick\` (or the targeted tests) -- anything regress?

Return "pass" ONLY if it genuinely clears the bar; else "needs-work" with specific, actionable findings (file, problem, fix).`,
      { label: `review:${x.u.slug}`, phase: 'Review', agentType: 'pr-review-toolkit:code-reviewer', schema: REVIEW_SCHEMA },
    ).then((review) => ({ ...x, review }))
  },

  (x) => {
    if (!x || !x.impl) return null
    if (x.review && x.review.verdict === 'pass') return { ...x, repaired: false }
    return agent(
`Repair issue(s) ${x.u.issues.map((n) => '#' + n).join(', ')} on branch \`${x.u.slug}\` (worktree "${WT(x.u.slug)}"): a review found problems. Fix them.

## Findings
${JSON.stringify((x.review && x.review.findings) || x.review, null, 1).slice(0, 2500)}

## Do
- \`cd "${WT(x.u.slug)}"\`. If the branch has NO commits yet, the implementer's work was never committed -- recover it: redo/commit the change per the issue. Re-read the issue and \`git -C ~/code/press diff main...${x.u.slug}\`.
- Address every actionable finding under the same house laws (verifier+known-bad, wire new targets/docs, adapters, complexity, fail-before/pass-after tests).
- Verify with \`PYTHONPATH=src\` (the editable install points at main), then commit to ${x.u.slug} (\`--no-verify\` after a manual pass if the hook tests main's code). Confirm \`git log --oneline main..HEAD\`. Do NOT push. Same trailer:
${TRAILER}

Return what you fixed, anything unresolved and why, whether you committed, and the final check result.`,
      { label: `repair:${x.u.slug}`, phase: 'Repair', agentType: 'general-purpose', schema: REPAIR_SCHEMA },
    ).then((repair) => ({ ...x, repair, repaired: true }))
  },
)

return {
  selected: units.map((u) => ({ slug: u.slug, issues: u.issues, title: u.title })),
  excluded: (sweep && sweep.excluded) || [],
  results: results.filter(Boolean).map((x) => ({
    slug: x.u.slug,
    issues: x.u.issues,
    branch: x.u.slug,
    worktree: '~/code/press-worktrees/' + x.u.slug,
    committed: !!(x.impl && x.impl.committed),
    commitSha: x.impl ? x.impl.commitSha : null,
    alreadyDone: x.impl ? !!x.impl.alreadyDone : false,
    reviewVerdict: x.review ? x.review.verdict : 'no-review',
    branchHasCommits: x.review ? x.review.branchHasCommits : null,
    reviewFindings: x.review ? (x.review.findings || []).length : 0,
    repaired: !!x.repaired,
    repairSummary: x.repair ? x.repair.summary : null,
  })),
}
