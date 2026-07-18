export const meta = {
  name: 'art-direction',
  description: 'Read the manuscript, apply the design skills, and write art/commissions.md: finished paste-ready image-model prompts for cover, chapter plates, logomark, and author portrait',
  whenToUse: 'args: {root: absolute path to the book repository}. Run once the manuscript is stable enough to know its imagery. args: {maxPlates?: number (default 8)}',
  phases: [
    { title: 'Scout', detail: 'manuscript shape, metadata, design skills' },
    { title: 'Commission', detail: 'cover, plates per chapter, logomark, portrait' },
    { title: 'Curate', detail: 'select plates, audit every prompt against the skills' },
    { title: 'Write', detail: 'art/commissions.md' },
  ],
}

const A = (typeof args === 'string') ? JSON.parse(args) : (args || {})
const ROOT = A.root || '.'
const MAX_PLATES = A.maxPlates || 8
if (ROOT === '.') throw new Error('args.root is required: pass the absolute path of the book repository')

phase('Scout')
const scout = await agent(
`The book repository is at ${ROOT} (work there, not in the session directory).
1. List every chapter file under ${ROOT}/book/chapters/ in filename order, and for each give a two-sentence summary of its subject and strongest concrete image (a scene, object, or scenario a woodcut could depict).
2. Read ${ROOT}/config/metadata.yaml and report: title, subtitle, author, publisher, publisher-place, date, description, and trim if set.
3. Run \`press skills\` (or \`python3 -m press skills\`) from ${ROOT} and report the absolute paths of cover-design, plates-and-woodcuts, and press-logomark. If the press is not installed, look under a press checkout's src/press/data/skills.
4. List existing art: ${ROOT}/assets/cover.jpg, ${ROOT}/assets/press-logo.png, ${ROOT}/assets/author.jpg, ${ROOT}/assets/woodcuts/*.jpg, and ${ROOT}/art/commissions.md if present.`,
  { label: 'scout', phase: 'Scout', schema: { type: 'object', properties: {
      chapters: { type: 'array', items: { type: 'object', properties: {
        file: { type: 'string' }, summary: { type: 'string' } }, required: ['file', 'summary'] } },
      metadata: { type: 'object' },
      skills: { type: 'object', properties: {
        cover: { type: 'string' }, plates: { type: 'string' }, logomark: { type: 'string' } },
        required: ['cover', 'plates', 'logomark'] },
      existingArt: { type: 'array', items: { type: 'string' } },
    }, required: ['chapters', 'metadata', 'skills'] } }
)
log(`${scout.chapters.length} chapters, skills found, ${(scout.existingArt || []).length} existing art files`)

const BRIEF = `Book metadata (name every visible word from these facts VERBATIM in any prompt that shows text; text a prompt leaves implicit will be misspelled or invented): ${JSON.stringify(scout.metadata)}.`

phase('Commission')
const commissions = await parallel([
  () => agent(
`Commission the COVER for this book. First read in full the cover-design skill at ${scout.skills.cover} and follow its house idiom and its scars exactly.
${BRIEF}
Chapters for imagery: ${scout.chapters.map(c => c.summary).join(' | ')}
Produce ONE finished, paste-ready image-model prompt for the front board: cloth color chosen for this book, ruled gilt border, one central engraved emblem drawn from the book's strongest image, every line of cover text named verbatim in reading order (title, full subtitle with its OR clauses, author). Also state the target aspect ratio from the trim.`,
    { label: 'commission:cover', phase: 'Commission', schema: { type: 'object', properties: {
        prompt: { type: 'string' }, aspect: { type: 'string' }, rationale: { type: 'string' } },
      required: ['prompt', 'aspect'] } }),
  () => agent(
`Commission the PRESS LOGOMARK (imprint device). First read in full the press-logomark skill at ${scout.skills.logomark} and obey its restraint rules.
${BRIEF}
Produce ONE finished, paste-ready image-model prompt for a printer's-mark-tradition imprint device for the publisher named in the metadata: flat single-ink line art on transparency, suited to appear at 2.2in on a colophon. Name any text it carries verbatim (a device may carry none; say so if none).`,
    { label: 'commission:logomark', phase: 'Commission', schema: { type: 'object', properties: {
        prompt: { type: 'string' }, rationale: { type: 'string' } }, required: ['prompt'] } }),
  () => agent(
`Commission the AUTHOR PORTRAIT. First read in full the plates-and-woodcuts skill at ${scout.skills.plates} for the engraving idiom (the portrait uses the same wood-engraving voice: dense hatching, single ink, no gray washes, earnest register).
${BRIEF}
Produce ONE finished, paste-ready image-model prompt for a small engraved author portrait suitable for back matter or the landing page. No text in the image.`,
    { label: 'commission:portrait', phase: 'Commission', schema: { type: 'object', properties: {
        prompt: { type: 'string' }, rationale: { type: 'string' } }, required: ['prompt'] } }),
  ...scout.chapters.map(ch => () => agent(
`Commission ONE interior PLATE candidate for a single chapter. First read in full the plates-and-woodcuts skill at ${scout.skills.plates} and follow its commissioning rules (one idea per plate, joke in the subject, style dead serious, deliberate portrait or landscape).
${BRIEF}
The chapter: ${ch.file} — ${ch.summary}
Read the chapter at ${ROOT}/${ch.file} in full. Propose the single strongest plate: a period engraver's brief as a finished paste-ready prompt, a kebab-case filename (no extension), and a one-line caption in the book's voice. If the chapter genuinely offers no image worth engraving, say so and return an empty prompt.`,
    { label: `commission:${ch.file.split('/').pop()}`, phase: 'Commission', schema: { type: 'object', properties: {
        file: { type: 'string' }, prompt: { type: 'string' }, filename: { type: 'string' },
        caption: { type: 'string' }, rationale: { type: 'string' } }, required: ['file', 'prompt'] } }
  ).then(r => ({ ...r, file: ch.file }))),
])
const [cover, logomark, portrait, ...plateCandidates] = commissions
if (!cover || !logomark || !portrait) throw new Error('a core commission failed; rerun')
const plates = plateCandidates.filter(Boolean).filter(p => p.prompt)
log(`commissions in: cover, logomark, portrait, ${plates.length} plate candidates`)

phase('Curate')
const curated = await agent(
`You are curating the plate list for one book. Candidates (one per chapter, some chapters may have none):
${JSON.stringify(plates, null, 2)}
Select at most ${MAX_PLATES}, keeping the strongest and cutting near-duplicates (two plates of the same subject argue neither); keep chapter coverage spread. Then AUDIT every kept plate prompt plus these three prompts against their skills (read them: ${scout.skills.cover}, ${scout.skills.plates}, ${scout.skills.logomark}):
COVER: ${JSON.stringify(cover)}
LOGOMARK: ${JSON.stringify(logomark)}
PORTRAIT: ${JSON.stringify(portrait)}
For each prompt verify: visible words named verbatim and complete (cover must carry title, every OR clause of the subtitle, author exactly as metadata states them); engraving language (hatching, single ink) not "detailed illustration"; flat plate, no mockup or perspective for the cover; one idea per plate. Repair any prompt that fails and return the final set.`,
  { label: 'curate', phase: 'Curate', schema: { type: 'object', properties: {
      cover: { type: 'object', properties: { prompt: { type: 'string' }, aspect: { type: 'string' } }, required: ['prompt'] },
      logomark: { type: 'object', properties: { prompt: { type: 'string' } }, required: ['prompt'] },
      portrait: { type: 'object', properties: { prompt: { type: 'string' } }, required: ['prompt'] },
      plates: { type: 'array', items: { type: 'object', properties: {
        file: { type: 'string' }, filename: { type: 'string' }, prompt: { type: 'string' },
        caption: { type: 'string' } }, required: ['file', 'filename', 'prompt'] } },
      repairs: { type: 'string' },
    }, required: ['cover', 'logomark', 'portrait', 'plates'] } }
)
log(`curated: ${curated.plates.length} plates kept${curated.repairs ? '; repairs: ' + curated.repairs : ''}`)

phase('Write')
await agent(
`Write ${ROOT}/art/commissions.md (create the art/ directory if needed; preserve any "Accepted ..." lines from an existing file by carrying them over unchanged at the end under "## Acceptance record").
Structure:
# Commissions
One-line preamble: these prompts are finished and paste-ready for an image model; accept results with \`press art accept <file> --as <target>\`.
## Cover — target aspect, then the prompt in a fenced block.
## Plates — for each: heading with the kebab filename, the chapter it belongs to, the caption, intake line (\`press art accept <file> --as plate:<filename>\`), prompt in a fenced block.
## Logomark — intake line (--as logomark), prompt in a fenced block.
## Author portrait — intake line (--as portrait), prompt in a fenced block.
Content: ${JSON.stringify({ cover: curated.cover, plates: curated.plates, logomark: curated.logomark, portrait: curated.portrait })}
House law for this file: no em or en dashes (rewrite), straight quotes only, sentence-case headings. Return the word count.`,
  { label: 'write', phase: 'Write' }
)
return { plates: curated.plates.length, file: `${ROOT}/art/commissions.md` }
