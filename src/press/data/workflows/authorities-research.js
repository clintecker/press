export const meta = {
  name: 'authorities-research',
  description: 'Extract the claims of fact from the manuscript (exhaustive by default), research real sources for each, adversarially verify, and write config/authorities.yaml for the build to enforce',
  whenToUse: 'args: {root: absolute path to the book repository}. Run against a book repository whose chapters assert facts (historical, technical, numerical) that deserve attribution. args: {maxClaimsPerFile?: number (default 0 = exhaustive; a positive cap samples and the accounting discloses omissions)}',
  phases: [
    { title: 'Extract', detail: 'per-chapter claim harvest' },
    { title: 'Research', detail: 'find a real authority for each claim' },
    { title: 'Verify', detail: 'skeptics attack weak attributions' },
    { title: 'Ledger', detail: 'write authorities.yaml, prove the build accepts it' },
  ],
}

const A = (typeof args === 'string') ? JSON.parse(args) : (args || {})
const CAP = A.maxClaimsPerFile || 0
const ROOT = A.root || '.'
const PRESS = A.press || 'press'

if (ROOT === '.') throw new Error('args.root is required: pass the absolute path of the book repository')
phase('Extract')
const scout = await agent(
`The book repository is at ${ROOT} (work there, not in the session directory). List every manuscript file under its book/chapters/ and book/appendices/ in filename order (relative paths). Then read ${ROOT}/config/metadata.yaml (title, subtitle, description, keywords) and skim the opening paragraphs of the first two chapters, and state: subject, one sentence saying what this book is actually about; and sourceKinds, two to four kinds of authorities appropriate to THIS book's domain (e.g. for a legal history: case reports, statutes, legal encyclopedias). The press ships this workflow to arbitrary books; nothing about any particular trade may be assumed.`,
  { label: 'scout', phase: 'Extract',
    schema: { type: 'object', properties: { files: { type: 'array', items: { type: 'string' } }, subject: { type: 'string' }, sourceKinds: { type: 'array', items: { type: 'string' } } }, required: ['files', 'subject', 'sourceKinds'] } }
)
const harvested = await parallel(scout.files.map(f => () => agent(
`Read ${ROOT}/${f} closely. Extract every CLAIM OF FACT the text asserts about the real world: historical practices, trade customs, terminology origins, dates, numbers, technical assertions about how things worked. NOT the author's own opinions, doctrines, or workshop practices; only statements a skeptical reader could ask "says who?" about.

For each claim return:
- fragment: a SHORT exact quote from the file (5-15 words, verbatim, no ellipses) that pins the claim to the text
- assertion: one sentence stating what the text claims as fact
${CAP ? `Rank by how strong and checkable the assertion is; return at most ${CAP} claims AND totalFound, the full count you identified, so the accounting can disclose what the cap omitted.` : 'Return EVERY claim you identify; exhaustiveness is the contract. Set totalFound to the same count.'} An empty list is correct for files that assert nothing.`,
  { label: `extract:${f.split('/').pop()}`, phase: 'Extract',
    schema: { type: 'object', properties: { claims: { type: 'array', items: { type: 'object', properties: { fragment: { type: 'string' }, assertion: { type: 'string' } }, required: ['fragment', 'assertion'] } }, totalFound: { type: 'number' } }, required: ['claims', 'totalFound'] } }
).then(r => ({ file: f, claims: (r.claims || []).map(c => ({ ...c, file: f })), totalFound: r.totalFound || (r.claims || []).length }))))
const missedFiles = scout.files.filter((f, i) => !harvested[i])
if (missedFiles.length) log(`extraction agents failed for ${missedFiles.length} file(s): ${missedFiles.join(', ')}; their claims are uncounted, rerun to cover them`)
const kept = harvested.filter(Boolean)
const claims = kept.flatMap(r => r.claims)
const omittedByCap = kept.reduce((n, r) => n + Math.max(0, r.totalFound - r.claims.length), 0)
log(`${claims.length} factual claims harvested${CAP ? ` (cap ${CAP}/file; ${omittedByCap} identified claims omitted by the cap)` : ' (exhaustive; nothing omitted)'}`)

phase('Research')
const researched = await parallel(claims.map(c => () => agent(
`You are sourcing one factual claim from a book. SUBJECT: ${scout.subject}

CLAIM (as the text asserts it): ${c.assertion}
EXACT TEXT FRAGMENT: "${c.fragment}" (in ${ROOT}/${c.file})

Use web search to find a real, checkable authority: a published book, scholarly article, museum or archive page, or standard reference that supports the claim. Prefer primary or classic sources over blogs; for this book's domain that means ${scout.sourceKinds.join(', ')}. Then judge honestly:
- If the claim is supported: give the authority as a short citation (author, title, year; add publisher or archive only if needed to find it), a stable url (the canonical page, archive record, or DOI; omit only if the work has no durable online locator), and one dry line on what it establishes.
- If the claim is PARTLY right or commonly repeated but disputed: say so and give the best source with a caveat note.
- If you cannot find real support: verdict "unsupported". Do not invent citations; an invented authority is worse than none.`,
  { label: `research:${c.fragment.slice(0, 24)}`, phase: 'Research',
    schema: { type: 'object', properties: { verdict: { enum: ['supported', 'caveat', 'unsupported'] }, authority: { type: 'string' }, url: { type: 'string' }, note: { type: 'string' } }, required: ['verdict'] } }
).then(r => ({ ...c, ...r }))))
// A null agent result is a failed lookup, not a cleared claim: it
// goes to the unresolved list, never silently out of the ledger.
const unresolved = claims.filter((c, i) => !researched[i]).map(c => ({ ...c, stage: 'research agent failed' }))
const sourced = researched.filter(Boolean)
log(`${sourced.filter(x => x.verdict !== 'unsupported').length}/${sourced.length} claims sourced; ${unresolved.length} unresolved`)

phase('Verify')
const attackable = sourced.filter(x => x.verdict !== 'unsupported')
const verified = await parallel(attackable.map(c => () => agent(
`Adversarially audit one attribution. CLAIM: ${c.assertion}
PROPOSED AUTHORITY: ${c.authority || 'none'}
NOTE: ${c.note || 'none'}

Attack it: does this source actually exist (search for it), and does it actually support THIS claim rather than something nearby? If the citation is real and on point, verdict "holds". If the source exists but the claim overstates it, verdict "overstates" with a corrected note. If the source looks invented or irrelevant, verdict "fails".`,
  { label: `audit:${c.fragment.slice(0, 24)}`, phase: 'Verify',
    schema: { type: 'object', properties: { verdict: { enum: ['holds', 'overstates', 'fails'] }, correctedNote: { type: 'string' } }, required: ['verdict'] } }
).then(r => ({ ...c, audit: r.verdict, note: r.verdict === 'overstates' ? r.correctedNote : c.note }))))
unresolved.push(...attackable.filter((c, i) => !verified[i]).map(c => ({ ...c, stage: 'audit agent failed' })))
const good = verified.filter(Boolean).filter(x => x.audit !== 'fails')
const unsourced = [
  ...sourced.filter(x => x.verdict === 'unsupported'),
  ...verified.filter(Boolean).filter(x => x.audit === 'fails'),
]
log(`reconciled: ${claims.length} harvested = ${good.length} ledgered + ${unsourced.length} unsourced + ${unresolved.length} unresolved`)

phase('Ledger')
const result = await agent(
`Work in the book repository at ${ROOT}. Write its table of authorities and prove the build accepts it.

1. Write ${ROOT}/config/authorities.yaml as a YAML list; for each entry below use keys claim (the exact fragment), file (the manuscript path as given), authority, url (omit if none), and note (omit if empty). The build validates this exact schema: the claim must appear exactly once in its declared file. Keep the fragments EXACTLY as given; the build verifies them against the text and fails on any mismatch. If a fragment does not appear verbatim in its file (check with grep after whitespace-normalizing), shorten it to a substring that does.

ENTRIES:
${JSON.stringify(good.map(x => ({ claim: x.fragment, file: x.file, authority: x.authority, url: x.url || '', note: x.note || '' })), null, 2)}

2. Run \`${PRESS} pdf\` from ${ROOT}. If the authorities generator rejects a claim, fix that entry's fragment and rerun until the build passes.

3. Report the claims that could NOT be sourced (below). Do NOT put them in the ledger; instead list them in your return so the author can decide whether to soften or cut those sentences:
${JSON.stringify(unsourced.map(x => ({ file: x.file, fragment: x.fragment, assertion: x.assertion })), null, 2)}

4. Also report the UNRESOLVED claims (below): their research or audit agent failed, so they are neither ledgered nor cleared. List them under their own heading with the failed stage; the author should rerun the workflow or source them by hand.
${JSON.stringify(unresolved.map(x => ({ file: x.file, fragment: x.fragment, assertion: x.assertion, stage: x.stage })), null, 2)}

Return: entries written, build status, the unsourced list with a one-line suggested edit for each, and the unresolved list verbatim.`,
  { label: 'ledger', phase: 'Ledger' }
)
return { subject: scout.subject, claims: claims.length, sourced: good.length, unsourced: unsourced.length, unresolved: unresolved.length, omittedByCap, extractionMissedFiles: missedFiles, ledger: result }