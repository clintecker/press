export const meta = {
  name: 'editorial-passes',
  description: 'Iterative editorial machine: per-chapter skill passes and whole-book passes produce suggestions, synthesizers apply them, mechanical law closes each round',
  whenToUse: 'args: {root: absolute path to the book repository}. Run against a book repository after composing or substantially revising chapters. args: {rounds?: number (default 2), maxims?: number (default 2), report?: boolean (suggestions written to build/editorial-report.md, nothing applied)}',
  phases: [
    { title: 'Scout', detail: 'find the manuscript and the skills' },
    { title: 'Suggest', detail: 'per-chapter skill lenses + whole-book lenses, suggestions only' },
    { title: 'Synthesize', detail: 'one synthesizer per chapter applies its suggestions' },
    { title: 'Law', detail: 'press check until green' },
  ],
}

const A = (typeof args === 'string') ? JSON.parse(args) : (args || {})
const ROOT = A.root || '.'
const REPORT = !!A.report
const ROUNDS = REPORT ? 1 : (A.rounds || 2)
const MAXIMS = A.maxims ?? 2

if (ROOT === '.') throw new Error('args.root is required: pass the absolute path of the book repository')
phase('Scout')
const scout = await agent(
`The book repository is at ${ROOT} (work there, not in the session directory). Report its shape:
1. List every manuscript file under its book/chapters/ and book/appendices/, in filename order (paths relative to ${ROOT}).
2. Find the four prose skills (humanizer, onwritingwell, elems_of_style, hemingway): run \`press skills\` (or \`python3 -m press skills\`) from ${ROOT} and use the paths it prints. Only if the press is not installed, look under a press checkout's src/press/data/skills. Report the absolute paths of the four files.
3. Read ${ROOT}/config/metadata.yaml and report the verify-sentinels list (exact strings that must survive any revision).
4. Read ${ROOT}/config/house-rules.yaml if present and report banned-patterns labels and jargon-allow.`,
  { label: 'scout', phase: 'Scout', schema: { type: 'object', properties: {
      files: { type: 'array', items: { type: 'string' } },
      skills: { type: 'array', items: { type: 'string' } },
      sentinels: { type: 'array', items: { type: 'string' } },
      houseRules: { type: 'string' },
    }, required: ['files', 'skills', 'sentinels'] } }
)
if (!scout.files.length) throw new Error('no manuscript files found')
log(`manuscript: ${scout.files.length} files, ${scout.skills.length} skills, ${scout.sentinels.length} sentinels`)

const LAW = `HOUSE LAW (mechanical, build-enforced): no em or en dashes anywhere (rewrite the sentence), straight quotes only, sentence-case headings, no manual heading numbers, ASCII plus accented latin only, paragraphs under 190 words, no trailing whitespace. Additional bans for this book: ${scout.houseRules || 'none beyond the universal rules'}. These exact sentinel strings must survive verbatim wherever they occur: ${JSON.stringify(scout.sentinels)}.`

const DISEASES = `THE NAMED DISEASES of agent prose (hunt these specifically; generic "improve the writing" advice is worthless):
1. Epigram compulsion: paragraphs that close on coined maxims. QUOTA: at most ${MAXIMS} coined maxims per chapter; every other one demoted to plain statement or cut. A paragraph is allowed to just end.
2. Uniform rhetorical rhythm: X-not-Y antithesis, chiasmus, triplets recurring every few sentences; every sentence polished to the same sheen. Plain sentences must do plain work.
3. Self-annotation: clauses that grade the previous clause ("and that is the point", "which is exactly the lesson"). Cut them; trust the material.
4. Emblematic abstraction where grit belongs: prefer a real duration, count, or cost to a rounded gesture.
5. Throat-clearing, inflated significance, chatbot signposting, formulaic negative parallelism.`

let totalApplied = 0
for (let round = 1; round <= ROUNDS; round++) {
  phase('Suggest')
  log(`round ${round}: collecting suggestions`)

  const perChapter = scout.files.map(f => () => agent(
`Round ${round} editorial pass on ONE chapter of a book. First READ IN FULL each of these prose skills and hold all four at once:
${scout.skills.map(s => '- ' + s).join('\n')}

${DISEASES}
${LAW}

Now read ${ROOT}/${f} closely and produce SUGGESTIONS ONLY (do not edit the file): each with the exact current text (short quote), the proposed replacement or 'delete', and which skill or disease motivates it. Suggest nothing that changes facts, practices, rules, headings, image lines, or captions. Quality over quantity; an empty list is an acceptable answer for clean prose. Cap at 12.`,
    { label: `suggest:${f.split('/').pop()}`, phase: 'Suggest',
      schema: { type: 'object', properties: { file: { type: 'string' }, suggestions: { type: 'array', items: { type: 'object', properties: { current: { type: 'string' }, proposed: { type: 'string' }, reason: { type: 'string' } }, required: ['current', 'proposed', 'reason'] } } }, required: ['file', 'suggestions'] } }
  ).then(r => ({ ...r, file: f })))

  const wholeBook = [
    { key: 'cadence', prompt: 'Read the whole manuscript aloud in your head listening ONLY for cadence: runs of consecutive maxim-endings, stretches of identical sentence rhythm, patterned constructions recurring across chapters. Voice drift between chapters counts.' },
    { key: 'repetition', prompt: 'Hunt whole-book repetition: the same fact, joke, image, or lesson introduced as new in two places; the same distinctive phrase reused; two chapters claiming the same example.' },
    { key: 'arc', prompt: 'Judge the book as one argument: does each chapter earn its place and order, do transitions land, does any chapter contradict another in doctrine or detail, does the conceit (if the book sustains one) stay load-bearing rather than decorative?' },
  ].map(lens => () => agent(
`Whole-book ${lens.key} pass, round ${round}. Read EVERY file in order under ${ROOT}: ${scout.files.join(', ')}.
${lens.prompt}
${DISEASES}
${LAW}
Produce SUGGESTIONS ONLY (no edits): each names the file, quotes the exact current text, gives the proposed replacement or 'delete', and the reason. Cap at 15 total, ranked by severity.`,
    { label: `book:${lens.key}`, phase: 'Suggest',
      schema: { type: 'object', properties: { suggestions: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, current: { type: 'string' }, proposed: { type: 'string' }, reason: { type: 'string' } }, required: ['file', 'current', 'proposed', 'reason'] } } }, required: ['suggestions'] } }
  ))

  const results = (await parallel([...perChapter, ...wholeBook])).filter(Boolean)
  // Whole-book agents name files free-form; normalize every variant
  // (basename, absolute, ROOT-prefixed) to the canonical relative path
  // so one real file gets exactly one synthesizer and no suggestion is
  // silently lost to a path mismatch.
  const canonical = new Map()
  for (const f of scout.files) {
    canonical.set(f, f)
    canonical.set(`${ROOT}/${f}`, f)
    const base = f.split('/').pop()
    canonical.set(base, canonical.has(base) && canonical.get(base) !== f ? null : f)
  }
  const byFile = {}
  const unresolvable = []
  for (const r of results) {
    for (const s of (r.suggestions || [])) {
      const raw = s.file || r.file
      if (!raw) continue
      const file = canonical.get(raw) || canonical.get(String(raw).replace(/^\/+/, ''))
      if (!file) { unresolvable.push({ file: raw, reason: s.reason }); continue }
      ;(byFile[file] = byFile[file] || []).push(s)
    }
  }
  const count = Object.values(byFile).reduce((n, a) => n + a.length, 0)
  log(`round ${round}: ${count} suggestions across ${Object.keys(byFile).length} files`)
  if (unresolvable.length) log(`round ${round}: ${unresolvable.length} suggestion(s) named files outside the manuscript and were set aside: ${unresolvable.map(u => u.file).join(', ')}`)

  if (REPORT) {
    phase('Synthesize')
    await agent(
`Write ${ROOT}/build/editorial-report.md (create build/ if needed): an editorial report the author reads before deciding anything. Do NOT edit any manuscript file.
Organize by file in manuscript order; under each file list every suggestion with the exact current text quoted, the proposed replacement or 'delete', and the reason (which skill or disease). Open with a short summary: total counts, the dominant diseases found, and the two or three highest-value changes across the whole book. Close with anything the whole-book passes said about cadence, repetition, or arc that no single edit fixes. If there are zero suggestions, say so plainly: a clean bill of health is the report.
House law for the report file itself: no em or en dashes, straight quotes, sentence-case headings.
SUGGESTIONS BY FILE:
${JSON.stringify(byFile, null, 2)}
Return the total suggestion count.`,
      { label: 'report', phase: 'Synthesize' }
    )
    log(`report written: ${ROOT}/build/editorial-report.md (nothing applied)`)
    return { rounds: 1, totalApplied: 0, report: `${ROOT}/build/editorial-report.md`, suggestions: count }
  }

  if (count === 0) break

  phase('Synthesize')
  const applied = await parallel(Object.entries(byFile).map(([file, suggestions]) => () => agent(
`You are the synthesizer for ${ROOT}/${file}. Below are editorial suggestions from independent per-chapter and whole-book passes. Apply them with Edit, exercising judgment: adopt what improves the prose, reconcile conflicts, skip anything that would change facts, rules, headings, image lines, captions, or violate the law. Preserve the author's voice; do not add length.
${LAW}

SUGGESTIONS:
${JSON.stringify(suggestions, null, 2)}

Return the count you applied and the count you rejected with a one-line reason for the rejections.`,
    { label: `synth:${file.split('/').pop()}`, phase: 'Synthesize',
      schema: { type: 'object', properties: { applied: { type: 'number' }, rejected: { type: 'number' }, rejectionReasons: { type: 'string' } }, required: ['applied', 'rejected'] } }
  )))
  const appliedCount = applied.filter(Boolean).reduce((n, a) => n + a.applied, 0)
  totalApplied += appliedCount
  log(`round ${round}: ${appliedCount} suggestions applied`)

  phase('Law')
  await agent(
`In the book repository at ${ROOT}, run the mechanical law and settle it: execute \`press check\` (or \`python3 -m press check\`) from ${ROOT}. Fix every violation it reports by rewriting sentences (never by substituting other punctuation), rerun until green. Verify each sentinel string still exists in the manuscript: ${JSON.stringify(scout.sentinels)}. If one is missing, restore it faithfully in its original location. Return the final check output's last line.`,
    { label: `law:round${round}`, phase: 'Law' }
  )
  if (appliedCount < 5) break
}
return { rounds: ROUNDS, totalApplied }