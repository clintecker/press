---
name: human-writing
version: 2.0.0
description: Draft, revise, and audit prose so it sounds like a specific writer making deliberate choices rather than a generic assistant producing broadly applicable text. Preserves meaning, evidence, uncertainty, register, and genuine voice while removing common model-writing patterns.
license: CC-BY-SA-4.0
compatibility: any-agent
---

# Human writing

## Purpose

Write like a person with a reason to write.

The goal is not to defeat an AI detector, scatter contractions through the text, add typos, ban a punctuation mark, or manufacture eccentricity. The goal is prose shaped by purpose, evidence, taste, judgment, and a real relationship between writer and reader.

A human writer:

- chooses an angle;
- notices some details and ignores others;
- makes claims at a chosen level of certainty;
- spends words unevenly;
- uses the vocabulary of the subject;
- reveals a stance when the genre permits one;
- stops when the work is done.

Remove generic model-writing habits without inventing facts, experiences, opinions, quotations, sources, or personality.

## Modes

This skill supports three modes.

### Draft

Create new prose from supplied facts, notes, sources, and constraints.

### Revise

Rewrite supplied prose while preserving its meaning, factual content, stance, uncertainty, terminology, and intended effect.

### Audit

Identify model-like patterns, explain why they weaken the prose, and recommend focused changes without rewriting unless asked.

Determine the mode from the request. When revising, return only the finished revision unless the user asks for commentary, alternatives, or an audit trail.

## Non-goals

Do not:

- claim to determine whether a person or model wrote a passage;
- optimize text against an AI detector;
- introduce deliberate errors or awkwardness;
- invent autobiographical detail to make prose seem lived-in;
- add opinions the writer did not express;
- convert neutral reference prose into a personal essay;
- flatten a distinctive voice into generic simplicity;
- preserve paragraph count, sentence count, or formatting merely because the source used it;
- remove every instance of a watched word or construction;
- treat polished grammar, formal vocabulary, passive voice, curly quotes, or em dashes as proof of model authorship.

The patterns in this skill are editing diagnostics. Look for clusters, repetition, and misuse.

## Core principles

### 1. A human has a point

Know what the writer wants the reader to understand, feel, decide, or do.

A passage can be grammatically sound and still feel synthetic when it has no angle beyond "cover the topic comprehensively."

### 2. Specificity carries voice

Exact nouns, actions, dates, numbers, constraints, quotations, and observations do more work than decorative adjectives.

Specificity must come from the material. Never fabricate it.

### 3. Selection shows judgment

Do not give every subtopic equal weight. Include what matters to this writer, for this reader, in this situation.

Completeness is not the same as usefulness.

### 4. Truth outranks fluency

Separate fact, interpretation, and uncertainty. Attribute opinions. State gaps plainly. Never bridge a missing fact with plausible prose.

### 5. Plain verbs are strong

Use `is`, `are`, `has`, `does`, `said`, `wrote`, `used`, and `made` when they are accurate.

Do not replace them with `serves as`, `stands as`, `features`, `boasts`, or `represents` merely to sound polished.

### 6. Rhythm follows thought

Vary sentence and paragraph length because the content changes. Do not manufacture a short-long-short pattern or stack fragments to imitate spontaneity.

### 7. Tone follows the situation

Human writing can be neutral, formal, technical, blunt, warm, skeptical, funny, restrained, messy, or elegant.

There is no single "human" voice.

### 8. Preserve before adding

Preserve genuine roughness, humor, repetition, dialect, uncertainty, and odd detail when they belong to the writer.

Do not add fake roughness, fake humor, fake uncertainty, or fake detail.

## Establish the writing contract

Before drafting or revising, identify:

- **Writer:** Who is speaking? What can they truthfully claim firsthand?
- **Reader:** Who will read this? What do they already know?
- **Purpose:** What should change after they read it?
- **Material:** Which facts, examples, observations, and sources are available?
- **Stance:** What does the writer think? How certain are they?
- **Register:** How formal, technical, personal, warm, or terse should the prose be?
- **Constraints:** Length, format, terminology, legal limits, house style, and facts that must remain unchanged.

Reduce this to one private sentence:

> `[Writer] needs [reader] to [understand / decide / do] [specific thing], in [register], using only [available material].`

Ask for a missing detail only when it materially changes the result and cannot be handled with a reasonable, visible placeholder.

## Keep a fact ledger

Before writing, sort the available material into three groups.

### Known

Directly supplied, observed, calculated, or supported by a cited source.

Write these claims directly at the level of certainty the evidence supports.

### Interpreted

A conclusion, judgment, reaction, or synthesis drawn from known facts.

Attribute it to the writer or source when necessary.

### Unknown

Missing, ambiguous, disputed, unverified, or unavailable.

Do not turn an unknown into:

- a probable biography;
- an imagined motive;
- a stock explanation;
- a fake quotation;
- a plausible scene;
- a personal memory;
- an exact date, place, or number.

Use a placeholder only when the artifact cannot function without the missing value.

## Voice calibration

When the user supplies a genuine writing sample, analyze it before revising.

Notice:

- typical sentence lengths and how they vary;
- vocabulary and level of formality;
- contractions;
- paragraph openings;
- punctuation habits;
- repeated phrases or deliberate verbal tics;
- transition style;
- use of first person;
- humor, bluntness, understatement, or skepticism;
- how the writer signals uncertainty;
- details the writer tends to notice.

Match patterns supported by the sample. Do not caricature them.

If the writer says `stuff`, do not automatically upgrade it to `elements`. If the writer uses exact technical nouns, do not replace them with casual approximations. If the sample uses em dashes, fragments, or parenthetical asides effectively, preserve that possibility.

When no voice sample exists, use the register implied by the material and audience. Default to clear, direct prose, not an invented "opinionated human" persona.

## Drafting workflow

### 1. Choose the angle

Write one private sentence stating the real point.

Weak:

> Explain the migration comprehensively.

Useful:

> The migration removes the only stateful service from deployment, but the rollback plan is still weak.

The useful angle tells the draft what deserves space.

### 2. Start where the subject starts

Open with the fact, claim, request, scene, problem, or decision.

Cut throat-clearing such as:

- "In today's rapidly changing world..."
- "This subject has become increasingly important..."
- "It is worth noting that..."
- "The following provides a comprehensive overview..."
- "Let's dive into..."
- "Here is what you need to know..."
- "I hope this message finds you well..." when it is merely automatic.

A lead should earn the next sentence.

### 3. Give each paragraph one job

A paragraph may:

- make a claim;
- supply evidence;
- describe an event;
- explain a cause;
- draw a distinction;
- register a reaction;
- ask for an action;
- change the reader's understanding.

Do not force every paragraph into the same length or rhetorical shape.

### 4. Prefer evidence over evaluation

Replace praise, importance, and abstract impact with the fact that supports them.

Weak:

> The release was a pivotal milestone that underscored the project's influence.

Stronger:

> The release moved the parser into the default build and retired two older implementations.

If no concrete fact supports the evaluation, remove it or attribute it as opinion.

### 5. Write in the actual register

Use words the writer would plausibly use in this situation.

Preserve domain terminology, contractions, dry humor, bluntness, dialect, fragments, and unusual phrasing when supported by the writer or requested genre.

Do not polish every sentence to the same sheen.

### 6. Spend words unevenly

Compress routine context. Expand the surprising fact, disputed point, difficult tradeoff, concrete scene, or detail the writer actually cares about.

Equal treatment of every item often feels less thoughtful than selective depth.

### 7. End at the last useful sentence

Do not add:

- a generic recap;
- a hopeful future;
- a broad life lesson;
- a ceremonial conclusion;
- an invitation to continue;
- "I hope this helps."

Stop when the purpose is complete.

## Diagnostic pattern catalog

A watched pattern is not automatically wrong. Rewrite it when it is repeated, vague, unsupported, mismatched to the voice, or doing work that a concrete statement should do.

### 1. Inflated significance

Watch for:

- serves as a testament;
- marks a pivotal moment;
- plays a crucial role;
- reflects a broader trend;
- leaves an enduring legacy;
- shapes the evolving landscape;
- sets the stage for;
- represents a major shift;
- deeply rooted;
- focal point.

Problem:

The sentence inflates a fact by announcing its historical, symbolic, or cultural importance without showing the connection.

Fix:

Name the change, effect, audience, mechanism, or evidence. Ask, "How, exactly?" If the sentence cannot answer, cut it.

### 2. Notability by name-dropping

Watch for lists of media outlets, awards, institutions, followers, or "independent coverage" used as a substitute for a relevant claim.

Weak:

> Her work has appeared in several major publications.

Stronger:

> In a 2025 interview, she argued that the rule should apply to outcomes rather than implementation details.

Use the source for the fact it supports.

### 3. Superficial participial analysis

Watch for factual clauses followed by vague `-ing` phrases:

- highlighting;
- underscoring;
- reflecting;
- symbolizing;
- ensuring;
- fostering;
- contributing to;
- showcasing.

Weak:

> The library added two adapters, highlighting its commitment to interoperability.

Stronger:

> The library added adapters for SQLite and DuckDB.

If intent matters, attribute it:

> The maintainer said the adapters were added to support local analytics without another service.

### 4. Promotional prose

Watch for:

- boasts;
- vibrant;
- rich heritage;
- renowned;
- breathtaking;
- groundbreaking;
- nestled;
- in the heart of;
- world-class;
- seamless;
- commitment to excellence;
- must-visit;
- stunning.

Replace sales language with observable properties, measured results, named examples, or a sourced evaluation.

Marketing copy may use enthusiasm, but it should still identify the customer, problem, mechanism, and result.

### 5. Vague authority and weasel attribution

Watch for:

- experts say;
- observers note;
- critics argue;
- researchers are interested;
- industry reports suggest;
- many believe;
- several sources say.

Name the person, paper, organization, survey, or dataset.

If the source is unknown, state the claim as the writer's interpretation or remove it.

### 6. Speculative gap-filling

Watch for prose explaining away missing information:

- maintains a low profile;
- keeps personal details private;
- appears to have;
- likely grew up;
- it is believed that;
- specific details are scarce;
- based on available information.

State exactly what is unknown. Do not infer a motive, biography, or personality from the absence of sources.

### 7. Formulaic challenges and future prospects

Watch for sections that follow this shape:

> Despite its success, the project faces challenges. With continued innovation, it is well positioned for the future.

Name the current constraint, evidence, owner, and next decision.

> The index exceeds the memory budget on repositories above 10 million objects. The team must decide whether to shard it or replace the storage layer.

### 8. Vocabulary clusters

Check clusters of words such as:

`additionally`, `align`, `bolster`, `crucial`, `delve`, `enduring`, `enhance`, `foster`, `garner`, `highlight`, `interplay`, `intricate`, `key`, `landscape`, `meticulous`, `pivotal`, `robust`, `showcase`, `tapestry`, `testament`, `underscore`, `valuable`, `vibrant`.

Do not ban them.

For each occurrence, ask:

1. Is this the most ordinary accurate word?
2. What fact does it add?
3. Could the sentence state the thing directly?
4. Is the same register repeated nearby?

Keep exact words. Remove decorative ones.

### 9. Copula avoidance

Weak:

> Gallery 825 serves as the association's exhibition space and features four rooms.

Stronger:

> Gallery 825 is the association's exhibition space. It has four rooms.

Use elaborate verbs only when they add meaning.

### 10. Forced contrast and negative parallelism

Watch for:

- not only X, but also Y;
- not just X, but Y;
- not merely X;
- X is not a tool but a mirror;
- no guessing;
- no wasted motion.

Use contrast only when the reader might genuinely confuse the alternatives.

Weak:

> The patch is not merely a speed improvement; it is a rethinking of the data model.

Stronger:

> The patch changes the data model. The speedup is a side effect.

### 11. Automatic groups of three

Do not default to three adjectives, examples, sections, benefits, or concluding nouns.

Use the number the material requires. One exact example can beat a complete-looking trio.

### 12. Synonym cycling

Repeat the correct term.

If the object is a cache, keep calling it a cache. Do not rotate through `store`, `repository`, `layer`, and `mechanism` unless those words identify different things.

Repetition can improve clarity, rhythm, emphasis, and humor.

### 13. False ranges

Watch for `from X to Y` when X and Y are not endpoints on a meaningful scale or sequence.

Weak:

> The book travels from the Big Bang to dark matter, from dying stars to the cosmic web.

Stronger:

> The book covers the Big Bang, stellar evolution, dark matter, and large-scale structure.

### 14. Actorless or unnecessary passive constructions

Passive voice is not inherently bad.

Keep it when:

- the actor is unknown;
- the actor is irrelevant;
- the affected object is the paragraph's topic;
- the genre convention calls for it.

Rewrite when the passive hides responsibility or makes the action harder to understand.

Weak:

> The deadline was missed and the records were deleted.

Stronger, when the actor matters:

> The vendor missed the deadline and deleted the records.

Also repair subjectless product fragments when clarity improves:

> No configuration file needed.

becomes:

> You do not need a configuration file.

### 15. Filler and over-hedging

Compress:

- in order to → to;
- due to the fact that → because;
- at this point in time → now;
- in the event that → if;
- has the ability to → can;
- it is important to note that → remove it and state the fact.

Preserve uncertainty, but express it once and at the correct level.

Weak:

> It could potentially possibly be argued that...

Stronger:

> The policy may affect...

### 16. Signposting and announcements

Cut announcements that postpone the content:

- let's dive in;
- let's explore;
- let's break this down;
- here is what you need to know;
- now let us look at;
- without further ado.

Begin the explanation.

### 17. Persuasive-authority tropes

Watch for:

- the real question is;
- at its core;
- fundamentally;
- what really matters;
- the deeper issue;
- the heart of the matter.

These phrases often announce profundity before stating an ordinary claim.

Replace the ceremony with the claim.

### 18. Fragmented headers

Remove a one-line paragraph that merely repeats the heading.

Weak:

> ## Performance
>
> Speed matters.
>
> Slow pages cause users to leave.

Stronger:

> ## Performance
>
> Slow pages cause users to leave.

### 19. Diff-anchored prose

Unless the document is a changelog, release note, migration guide, or review, describe the thing as it is rather than narrating the last edit.

Weak:

> This function was added to replace the previous loop.

Stronger:

> This function uses a hash map for constant-time lookup.

### 20. Manufactured punchlines and staccato drama

One short sentence can land a point. A chain of clipped declarations often sounds engineered.

Weak:

> Then the new system arrived. No symmetry. No history. No compromise. Everything changed.

Stronger:

> The new system did not favor symmetry or earlier conventions, which made several old assumptions less useful.

Do not remove genuine dramatic rhythm from a writer who uses it intentionally.

### 21. Aphorism formulas

Watch for:

- X is the language of Y;
- X is the currency of Y;
- X is the architecture of Y;
- X becomes a trap;
- X is not a tool but a mirror.

Replace the reusable slogan with the concrete claim it gestures toward.

### 22. Fake-candid openers

Watch for theatrical openings such as:

- Honestly?
- Look,
- Here's the thing:
- Let's be honest.
- Real talk.

These phrases are ordinary in real speech. Rewrite them only when they manufacture intimacy before an unremarkable point.

### 23. Assistant residue and sycophancy

Remove text that manages a chat instead of serving the artifact:

- Of course;
- Certainly;
- Great question;
- You are absolutely right;
- Here is a detailed breakdown;
- I hope this helps;
- Would you like me to;
- Let me know if;
- references to the prompt, model, training data, or knowledge cutoff;
- editing instructions accidentally left in the prose.

Acknowledge the reader only when there is something real to acknowledge.

### 24. Generic positive conclusions

Weak:

> The future is bright as the company continues its journey toward excellence.

Stronger:

> The company plans to open two locations next year.

End with the next fact, decision, implication, image, request, or unresolved tension.

## Formatting diagnostics

Formatting should follow the medium, writer, and house style. Do not use formatting as an authorship test.

### Headings

- Prefer sentence case unless the house style requires title case.
- Use headings only when they help navigation or argument.
- Follow heading levels in order.
- Do not create a heading for every paragraph.

### Boldface and inline labels

Use bold for actual emphasis, not to decorate every bullet.

Avoid repeated `**Label:** explanation` lists when prose or a table would scan better.

### Lists and tables

Use lists for procedures, inventories, choices, or genuinely parallel items.

Use tables only when rows and columns reveal a useful comparison.

Do not force prose into bullets merely to appear organized.

### Emoji

Use emoji when the writer, audience, and medium support them. Do not add them as generic decoration.

### Dashes

Em dashes, en dashes, and parenthetical dashes are not inherently model-like.

Keep them when they match the writer and improve the sentence. Revise them when they recur mechanically, interrupt every sentence, or substitute for clearer syntax.

Respect a user or house-style ban when one exists.

### Quotation marks

Match the target environment and house style.

Curly quotes may be correct in publishing. Straight quotes may be correct in source code, Markdown, plain text, or a particular style guide. Do not convert them as an anti-AI ritual.

### Hyphenated compounds

Follow normal grammar and the house style.

Attributive compounds often take hyphens:

> a high-quality report

Predicate compounds often do not:

> the report is high quality

Do not alter technically meaningful forms such as `end-to-end encryption` merely to vary texture.

### Markup

Match the requested format. Do not leak Markdown into email, HTML into plain text, or editor instructions into finished copy.

## Human texture to preserve

These features often carry genuine voice. Preserve them unless they obstruct the purpose.

### Specific, unusual detail

Keep the detail that could only belong to this situation:

- the exact command that failed;
- the odd phrase someone used;
- the number that changed the argument;
- the physical behavior of an object;
- the constraint everyone worked around.

Never invent such a detail.

### Mixed feelings and unresolved tension

A writer may believe something is mostly good and still dislike one tradeoff. Do not force the tension into a clean verdict.

### Genuine asides and self-correction

Parentheticals, repetitions, false starts, and corrections can show thought in motion.

Keep them when they are already present or clearly fit the writer. Do not add them as costume.

### Era-bound references and in-jokes

Preserve references that locate the writer in a community, time, or relationship when the intended reader will understand them.

Do not inject trendy slang to simulate currency.

### Deliberate repetition

A repeated word or sentence shape may create emphasis, rhythm, precision, or a joke. Do not "fix" it automatically.

### Honest stance

First person can state:

- I think;
- I do not buy that argument;
- I was wrong;
- I do not know yet;
- this works, but I dislike the tradeoff.

Use first person only when the writer owns the statement.

## Genre adjustments

### Email and chat

- Start with the reason for writing.
- Make the request, decision, or update easy to find.
- Include the deadline, owner, or next step when relevant.
- Use greetings and sign-offs that fit the relationship.
- Avoid canned warmth and automatic gratitude.
- Do not make a normal workplace message sound like a press release.

### Technical documentation

- Lead with what the reader is trying to do.
- Keep exact terms stable.
- Show commands, inputs, outputs, constraints, and failure modes.
- Prefer direct descriptions over change narration.
- Use lists for procedures and tables for true comparisons.
- Neutral and plain is a valid human voice.

### Essays and reports

- Make a claim rather than touring the topic.
- Let evidence narrow or complicate the claim.
- Attribute opinions.
- Use section headings only when the argument needs them.
- Do not end every section with a miniature conclusion.

### Academic and encyclopedic prose

- Neutral does not mean vague or grand.
- Use simple copulas freely.
- Distinguish source claims from synthesis.
- Give precise citations when available.
- Do not infer consensus from a small number of sources.
- Do not inject first-person reactions or humor unless the genre permits it.

### Legal and policy prose

- Preserve defined terms and carefully chosen qualifications.
- Do not simplify away a material exception.
- Passive voice may be intentional when the legal actor is unspecified or irrelevant.
- Remove rhetorical inflation, not necessary precision.

### Marketing copy

- Name the audience, problem, mechanism, and result.
- Prefer demonstrations, numbers, limits, and comparisons to superlatives.
- Keep enthusiasm tied to something observable.
- Avoid calling every product effortless, powerful, flexible, seamless, or transformative.

### Personal and narrative writing

- Preserve the writer's real observations, reactions, chronology, and uncertainty.
- Do not add scenes, locations, dialogue, sensory details, or memories.
- Uneven attention is often part of the voice.
- A clean but unresolved ending may be better than a moral.

## Revision process

Run the passes internally. Do not expose every pass unless the user asks for an audit.

### Pass 1: Fidelity

- What must not change?
- Did the revision alter the writer's claim, stance, emotion, or certainty?
- Did it introduce any new fact, experience, opinion, source, or quotation?
- Did it omit necessary content?

### Pass 2: Purpose and selection

- What is the real point?
- Which paragraph exists only to make the piece look complete?
- What can the reader infer?
- Where should the piece go deeper instead of wider?

### Pass 3: Evidence and specificity

- Which evaluation needs a fact?
- Which abstraction can become a name, action, date, number, or example?
- Who owns each opinion?
- Which sentence could fit a hundred unrelated subjects?

### Pass 4: Syntax

- Restore simple verbs.
- Cut stacked participial phrases.
- Remove forced contrasts, false ranges, and automatic triads.
- Keep repeated technical terms.
- Split sentences carrying unrelated ideas.
- Clarify actors when responsibility matters.

### Pass 5: Voice

- Match the writer's vocabulary and level of formality.
- Preserve supported humor, dialect, bluntness, restraint, and roughness.
- Remove phrases the writer would never say.
- Check that no personality was invented.

### Pass 6: Structure and formatting

- Remove unnecessary headings, bold labels, tiny tables, and decorative sections.
- Match the target medium.
- Preserve useful organization without making every section symmetrical.

### Pass 7: Sound

Read the prose aloud or simulate doing so.

Ask:

- Where does the cadence become monotonous?
- Which sentence sounds written for every possible reader?
- Where does the prose explain what the reader already knows?
- Which sentence sounds impressive but says little?
- Does a sequence of short sentences manufacture drama?
- Does the ending stop cleanly?

### Pass 8: Verification

Check:

- names;
- dates;
- numbers;
- units;
- quotations;
- links;
- source attribution;
- technical terminology;
- the stated level of certainty.

Fluency does not excuse invention.

## Output behavior

### When drafting

- Produce the finished text in the requested format.
- Do not announce that you are about to write.
- Do not explain ordinary writing choices unless asked.
- Do not pad a short artifact into a long one.
- Do not add a closing offer.

### When revising

- Preserve meaning, coverage, stance, intensity, dialect, terminology, and uncertainty.
- Change structure when that improves the piece; do not preserve paragraph count mechanically.
- Do not make the writer kinder, harsher, funnier, more certain, or more formal without instruction.
- Return the final revision only unless the user asks for notes or alternatives.

### When auditing

Report:

1. the strongest patterns, ordered by impact;
2. why each pattern weakens this specific passage;
3. the smallest useful fix;
4. any sentence that should be preserved because it carries genuine voice.

Do not claim the text was written by AI.

### When information is incomplete

- State the exact gap.
- Separate fact from inference.
- Do not invent a likely explanation.
- Use visible placeholders only when necessary.

## Rewrite examples

### Significance inflation

Before:

> The new scheduler represents a pivotal advancement in the evolving orchestration landscape.

After:

> The new scheduler can pause a job, move it to another worker, and resume from the last checkpoint.

### Promotional language

Before:

> The neighborhood boasts a vibrant array of renowned dining destinations.

After:

> The six-block strip has 23 restaurants, including three that stay open past midnight.

### Forced contrast

Before:

> This is not just a cache; it is a robust foundation for scalable performance.

After:

> The cache removes repeated database reads. In the current load test, it cuts p95 latency by 38 percent.

### Vague attribution

Before:

> Experts have raised concerns about the policy's long-term effects.

After:

> In its June report, the state auditor said the policy could shift costs from the general fund to county budgets.

### Formulaic ending

Before:

> Despite these challenges, continued innovation will ensure a promising future.

After:

> The next release depends on replacing the abandoned encryption library. No maintainer owns that work yet.

### Synonym cycling

Before:

> The parser reads the file. The processing engine validates the document. This component returns an error report.

After:

> The parser reads the file, validates it, and returns an error report.

### Diff-anchored documentation

Before:

> This method was added to replace the previous iteration-based lookup.

After:

> This method uses a hash map for constant-time lookup.

### Assistant residue

Before:

> Certainly. Here is a polished version of the message. I hope this helps.

After:

> Return the message itself.

### Preserve uncertainty

Before:

> The evidence may perhaps suggest that the rollout was somewhat successful.

After:

> The rollout reduced support tickets, but the sample is too small to show whether the change will last.

### Do not invent humanity

Source:

> I spent five days in Lisbon. The hills were tiring, and I liked the pastries more than the castle.

Invalid revision:

> I stayed in Alfama last October and planned every walk around the six flights to my hotel.

The source does not provide the month, neighborhood, hotel, or behavior.

Valid revision:

> I spent five days in Lisbon. The hills wore me out, and I liked the pastries more than the castle.

## Final checklist

Before returning prose, verify:

- The first sentence begins the work.
- The piece has a clear purpose and angle.
- Concrete material carries the main claims.
- Opinions have owners.
- Unknowns remain unknown.
- No fact, memory, scene, quotation, or preference was invented.
- Simple verbs have not been polished away.
- Lists and contrasts use the number the material requires.
- Repeated terms remain stable when precision matters.
- Formatting serves the reader and medium.
- Watched patterns were judged in context, not banned mechanically.
- Genuine voice was preserved rather than simulated.
- No chatbot residue remains.
- The last sentence is the actual ending.

## Scoring rubric

Score each category from 0 to 2.

- **Fidelity:** Meaning, facts, stance, and certainty are preserved.
- **Purpose:** The piece knows what it is trying to do.
- **Specificity:** Claims rest on concrete supplied material.
- **Selection:** The piece includes what matters and omits filler.
- **Voice:** The prose is plausible for this writer, reader, and genre.
- **Rhythm:** Sentence and paragraph shapes follow the thought.
- **Honesty:** Facts, interpretations, and unknowns remain distinct.

A strong result scores at least 12 out of 14 and has no fatal defect.

Fatal defects:

- invented fact, source, quote, experience, memory, scene, or preference;
- unsupported sweeping claim;
- changed meaning, stance, or certainty;
- generic filler carrying the main argument;
- flattened or fabricated voice;
- visible assistant instructions or placeholder residue.
