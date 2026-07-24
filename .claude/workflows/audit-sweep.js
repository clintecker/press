// Audit the press for real, actionable defects across several angles at once,
// then adversarially verify each finding before it is reported, so a plausible
// but wrong finding never reaches the board. Returns a ranked, deduped,
// CONFIRMED-only list; I file the survivors as issues myself.
//
// Reusable: Workflow({ name: "audit-sweep" }) or with
// { scriptPath: ".claude/workflows/audit-sweep.js" }.
export const meta = {
  name: 'audit-sweep',
  description: 'Audit the press across correctness, boundary, test, docs/site, and security angles; adversarially verify each finding; report only confirmed defects for triage',
  phases: [
    { title: 'Find', detail: 'one agent per audit angle, in parallel' },
    { title: 'Verify', detail: 'each finding independently refuted-or-confirmed' },
  ],
}

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          title: { type: 'string' },
          severity: { type: 'string', enum: ['high', 'medium', 'low'] },
          file: { type: 'string' },
          line: { type: 'number' },
          evidence: { type: 'string' },
          failure: { type: 'string' },
          fix: { type: 'string' },
        },
        required: ['title', 'severity', 'file', 'evidence', 'failure'],
      },
    },
  },
  required: ['findings'],
  additionalProperties: true,
}
const VERDICT_SCHEMA = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['confirmed', 'refuted', 'unsure'] },
    reason: { type: 'string' },
    reproduced: { type: 'boolean' },
    corrected_severity: { type: 'string', enum: ['high', 'medium', 'low'] },
    notes: { type: 'string' },
  },
  required: ['verdict', 'reason'],
  additionalProperties: true,
}

const HOUSE = `The press is a pip-installable book build/check/verify pipeline. House laws that shape what counts as a defect: a checker is only real with a known-bad fixture it REJECTS; boundaries (subprocess/env/network) route through press.adapters and nothing may reach them outside that package; a new public callable is classified in quality/surfaces.yaml and a new target/config/doc lands in the same commit as its docs (press selftest --write-docs); design (typography/layout of a valid book) is fixed only across a major; the docs site (site/press.css) is the press's own and not bound by a book's contract. Read CLAUDE.md before judging what is in-bounds.`

const ANGLES = [
  {
    key: 'correctness',
    prompt: `Audit the press Python package (src/press/) for CORRECTNESS defects an existing test does not already catch: a wrong result on a real input, an unhandled edge (empty/None/duplicate/unicode/boundary value), a swallowed error, an off-by-one, a resource read unbounded, a regex that matches too much or too little, a comparison that should be identity, a cache that outlives its key. Prefer the impure orchestration modules (build, verify_*, gen_*, commerce, edition, qualification, idlookup, receipts) where logic is densest. For each, cite file:line, give the exact input that misbehaves and the wrong output/crash, and a fix. Do NOT report style, naming, or "could be clearer" -- only defects with a concrete failing case.`,
  },
  {
    key: 'boundary',
    prompt: `Audit the typed adapter boundary (tests/test_adapters_boundary.py is the gate; src/press/adapters/ is the one approved home). #199 just removed the last legacy allowlist entry, so the invariant is: NO direct subprocess / os.environ / os.getenv / shutil.which / urllib / requests call anywhere in src/press outside the adapters package. Hunt for: a call that slips the AST matcher (e.g. 'from subprocess import run' aliasing, os.environ via a re-export, a getattr), a boundary reached through a helper that the gate cannot see, an adapter whose fake and production implementations have DIFFERENT behaviour (a contract violation), or a place that reads os.environ-equivalent state through a side door. Cite file:line and show the reachable path. A finding must be a real escape or divergence, not a theoretical one.`,
  },
  {
    key: 'tests',
    prompt: `Audit the test suite (tests/) for GAPS that let a real regression pass green: a checker/verifier with no known-bad fixture that reddens it (house law violation), an assertion that only checks "it ran" rather than an active signal (value/typed finding/exception/recorded adapter call), a test whose fixture is so loose it would pass even if the code were wrong, a public behaviour with no negative/adversarial case, a mutation the mutation ratchet would miss. Prefer verifiers and gates where a false green is most dangerous. For each, name the file:line of the weak/absent test, the specific regression it would fail to catch, and the missing case. Do NOT report "add more tests" in the abstract -- name the exact uncovered failure.`,
  },
  {
    key: 'docs-site',
    prompt: `Audit the docs site and generated documentation for DEFECTS and DRIFT. Two parts: (1) scripts/build_site.py + site/press.css -- responsive/layout bugs of the class just fixed (an element that collapses or overflows at some viewport/zoom, a selector specificity collision, a silent font fallback, a focus state missing, a theme that breaks), and content/link drift. (2) The generated docs (docs/*.md, REFERENCE, INVARIANTS, GALLERY) vs the code they describe -- a documented flag/target/config key that no longer exists, a command example that would fail, a stated default that is wrong, a claim the code contradicts. The docs site is the press's OWN site (not a book), so responsive fixes there are in-bounds. Cite file:line and the exact wrong text or the viewport/selector at fault.`,
  },
  {
    key: 'security',
    prompt: `Audit for SECURITY and safety defects in the press's own handling (not GitHub settings -- those are tracked). Look for: a path built from config/metadata that could escape the book root or dist/ (the slug invariant is the guard -- find a bypass), a source archive that could include a secret-prone or symlinked file the refusal misses, HTML/TeX/YAML interpolation of book metadata that is not escaped (an injection into a generated page, cover, or CI output), a network response parsed without bounds or with entity expansion, a subprocess argv built from untrusted text without proper listing, a temp file or world-readable write. The threat model is a hostile book repo and a hostile network response, NOT a hostile local operator. Cite file:line, the injected value, and what it reaches.`,
  },
]

// ---- FIND -> VERIFY, per angle, pipelined -----------------------------------
const perAngle = await pipeline(
  ANGLES,

  (a) => agent(
`${HOUSE}\n\nYou are the ${a.key} auditor. Read the relevant code in ~/code/press with fresh eyes -- do not trust that existing tests or prior audits caught everything.\n\n${a.prompt}\n\nReturn up to 8 of your STRONGEST findings, most severe first. Each needs a concrete failing case (the input and the wrong outcome), not a smell. If you find nothing real, return an empty list -- a false finding is worse than none.`,
    { label: `find:${a.key}`, phase: 'Find', agentType: 'general-purpose', schema: FINDINGS_SCHEMA },
  ).then((r) => ({ angle: a.key, findings: (r && r.findings) || [] })),

  (r) => {
    if (!r || !r.findings.length) return { angle: r ? r.angle : '?', verified: [] }
    return parallel(r.findings.map((f) => () =>
      agent(
`${HOUSE}\n\nAdversarially verify this ${r.angle} audit finding against the real code in ~/code/press. Your DEFAULT is "refuted": assume it is wrong until you reproduce it.\n\nFinding: ${f.title}\nSeverity claimed: ${f.severity}\nLocation: ${f.file}${f.line ? ':' + f.line : ''}\nEvidence: ${f.evidence}\nClaimed failure: ${f.failure}\n${f.fix ? 'Proposed fix: ' + f.fix : ''}\n\nRead the cited code AND its callers and tests. Confirm ONLY if you can point to the exact line that fails and describe the concrete input that triggers it and the wrong result -- and confirm no existing test or guard already prevents it (a finding a test already catches is refuted). Reassess the severity honestly. Return verdict confirmed | refuted | unsure, your reason, whether you reproduced it, and a corrected severity.`,
        { label: `verify:${r.angle}:${(f.file || '').split('/').pop()}`, phase: 'Verify', agentType: 'general-purpose', schema: VERDICT_SCHEMA },
      ).then((v) => ({ ...f, angle: r.angle, verdict: v }))
    )).then((vs) => ({ angle: r.angle, verified: vs.filter(Boolean) }))
  },
)

// ---- collect CONFIRMED survivors, ranked ------------------------------------
const order = { high: 0, medium: 1, low: 2 }
const confirmed = perAngle
  .filter(Boolean)
  .flatMap((r) => r.verified)
  .filter((f) => f.verdict && f.verdict.verdict === 'confirmed')
  .map((f) => ({
    angle: f.angle,
    title: f.title,
    severity: (f.verdict.corrected_severity || f.severity),
    file: f.file,
    line: f.line || null,
    failure: f.failure,
    fix: f.fix || null,
    reproduced: !!f.verdict.reproduced,
    reason: f.verdict.reason,
  }))
  .sort((a, b) => (order[a.severity] ?? 3) - (order[b.severity] ?? 3))

const raw = perAngle.filter(Boolean).reduce((n, r) => n + r.verified.length, 0)
log(`audit: ${raw} findings surfaced, ${confirmed.length} confirmed after adversarial verify`)

return {
  confirmed,
  byAngle: perAngle.filter(Boolean).map((r) => ({
    angle: r.angle,
    surfaced: r.verified.length,
    confirmed: r.verified.filter((f) => f.verdict && f.verdict.verdict === 'confirmed').length,
  })),
}
