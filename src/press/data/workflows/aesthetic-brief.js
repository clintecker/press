export const meta = {
  name: 'aesthetic-brief',
  description: 'Turn an author brief ("1970s cheesy sci-fi paperback") into config/aesthetic.yaml: read the manuscript, draft the identity per the book-aesthetics skill, audit it for coherence, write the file',
  whenToUse: 'args: {root: absolute path to the book repository, brief: the author\'s description of the look}. args: {overwrite?: boolean (default false)}',
  phases: [
    { title: 'Scout', detail: 'manuscript gist, the skill, the current aesthetic' },
    { title: 'Draft', detail: 'the identity, per schema' },
    { title: 'Audit', detail: 'coherence and craft-language check, then write' },
  ],
}

const A = (typeof args === 'string') ? JSON.parse(args) : (args || {})
const ROOT = A.root || '.'
const BRIEF = A.brief || ''
const OVERWRITE = !!A.overwrite
if (ROOT === '.') throw new Error('args.root is required: pass the absolute path of the book repository')
if (!BRIEF) throw new Error('args.brief is required: describe the look the author wants')

phase('Scout')
const scout = await agent(
`The book repository is at ${ROOT}.
1. Report whether ${ROOT}/config/aesthetic.yaml already exists.
2. Give a five-sentence gist of the manuscript under ${ROOT}/book/chapters/ (subject, voice, era of the material).
3. Run \`press skills\` (or \`python3 -m press skills\`) from ${ROOT} and report the path of the book-aesthetics skill.
4. Run \`press aesthetic\` from ${ROOT} and report its output (the currently effective identity).`,
  { label: 'scout', phase: 'Scout', schema: { type: 'object', properties: {
      exists: { type: 'boolean' }, gist: { type: 'string' },
      skill: { type: 'string' }, current: { type: 'string' },
    }, required: ['exists', 'gist', 'skill'] } }
)
if (scout.exists && !OVERWRITE) {
  throw new Error(`${ROOT}/config/aesthetic.yaml already exists; pass args.overwrite: true to replace it`)
}

phase('Draft')
const draft = await agent(
`Read in full the book-aesthetics skill at ${scout.skill}: it states the schema, what is configurable, and what craft language means.
THE AUTHOR'S BRIEF: ${BRIEF}
THE MANUSCRIPT: ${scout.gist}
Draft the complete config/aesthetic.yaml for this book: every schema section (name, register, cover with all six fields, plates, logomark, portrait, AND the page look: web-palette and web-palette-dark with hex values for the reader tokens, typography with web-family and pdf-family, book-colors with ink/muted/accent/link), values in concrete craft language a period art director would use, faithful to the brief and fitting the manuscript. The page look is where most briefs live or die: a pulp paperback brief with the Victorian house palette left in place is a failed draft. Return the YAML text only.`,
  { label: 'draft', phase: 'Draft', schema: { type: 'object', properties: {
      yaml: { type: 'string' }, rationale: { type: 'string' } }, required: ['yaml'] } }
)

phase('Audit')
await agent(
`You are auditing a drafted aesthetic before it is written. The skill: read ${scout.skill} in full.
THE BRIEF: ${BRIEF}
THE DRAFT:
${draft.yaml}
Verify: valid YAML matching the skill's schema; every value concrete craft language, no bare adjectives ("cool", "vintage"); internally coherent era and medium; register one or two sentences; nothing attempting to configure away craft law (verbatim text, flat plates, single-ink interiors). Repair what fails. Then write the final text to ${ROOT}/config/aesthetic.yaml (create config/ if needed) with a two-line header comment naming the brief it came from, and confirm by running \`press aesthetic\` from ${ROOT} and returning its first ten lines.`,
  { label: 'audit', phase: 'Audit' }
)
return { file: `${ROOT}/config/aesthetic.yaml`, brief: BRIEF }
