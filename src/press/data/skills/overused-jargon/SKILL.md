---
name: overused-jargon
version: 1.0.0
description: Detect and remove overused, overloaded, metaphorical, or model-favored jargon without deleting necessary technical terms or flattening the writer's voice. Use for plain-language edits, technical writing, model-output cleanup, watchlist maintenance, and discovery of new verbal tics across a corpus.
license: CC0-1.0
compatibility: any-agent
---

# Overused and overloaded jargon

## Purpose

Remove words and phrases that sound technical or decisive but hide the literal claim.

This skill targets model-favored language such as:

- stock engineering metaphors;
- insider shorthand;
- fashionable business language;
- vague verdict words;
- repeated status verbs;
- abstractions that conceal the actor, action, condition, scope, or consequence.

The goal is not to make every sentence casual or simple. The goal is to make each term earn its place.

Preserve exact technical language, direct quotations, code, identifiers, legal terms, scientific terms, and deliberate voice.

## Modes

Infer the mode from the request.

### Draft

Write new prose while avoiding watched terms and the habits that produce them.

### Revise

Replace jargon with literal claims while preserving meaning, facts, uncertainty, tone, and necessary terminology.

### Audit

Identify the strongest problems and propose focused repairs without rewriting unless asked.

### Discover

Analyze a collection of model outputs against a human or domain baseline and propose new watch terms.

### Maintain

Add, change, or remove watchlist entries after reviewing real examples.

## Governing rule

A watchlist match starts a review. It does not decide the edit.

Keep a term only when all of these are true:

1. It has one clear meaning in the sentence.
2. It is standard for the intended reader, or the text defines it.
3. It is more precise than an ordinary alternative.
4. It does not replace the actor, action, condition, scope, evidence, or consequence.
5. Its repetition is necessary or deliberate.

Otherwise, rewrite it.

When the house style explicitly bans a term, follow the ban even if the term could be defensible elsewhere.

## Definitions

### Overused

A word or phrase appears often enough that it becomes a mannerism rather than a choice.

### Overloaded

A term carries several possible meanings and leaves the reader to guess which one applies.

Examples:

- `gate` may mean a test, approval, dependency, feature flag, deadline, or person with authority;
- `surface` may mean display, reveal, expose, return, mention, or make available;
- `clean` may mean correct, formatted, empty, safe, passing, quiet, or merely pleasing.

### Stock metaphor

A metaphor used as if it were an exact technical description.

Examples:

- `load-bearing`;
- `blast radius`;
- `spine`;
- `seam`;
- `scaffold`;
- `substrate`;
- `wiring`.

### Verdict word

A word that announces certainty, quality, or importance without giving the evidence.

Examples:

- `decisive`;
- `authoritative`;
- `healthy`;
- `cleanly`;
- `genuinely`;
- `proves`;
- `verified`.

### Insider shorthand

A phrase that may be clear inside one group but makes other readers decode the sentence.

Examples:

- `footgun`;
- `yak shaving`;
- `belt-and-suspenders`;
- `ship it`;
- `landed`;
- `blocker`.

### Model tic

A word or construction that recurs across model output often enough to sound borrowed.

Do not claim that a tic proves who wrote the text. Treat it only as an editing signal.

## What not to change

Do not rewrite:

- text inside direct quotations unless the user asks;
- source code, commands, paths, identifiers, API names, or interface labels;
- a defined legal, scientific, or technical term whose replacement would lose meaning;
- literal uses, such as a load-bearing wall or a seam in a coat;
- a phrase that clearly belongs to the writer's established voice;
- a repeated term that prevents ambiguity;
- a necessary warning, qualification, or statement of uncertainty.

Plain language does not mean imprecise language.

## Detection

Run these checks before editing.

### 1. Watchlist check

Search the text against `references/watchlist.csv`.

The default statuses are:

- `rewrite`: replace unless a listed exception clearly applies;
- `inspect`: review in context;
- `ban`: remove under the current house style;
- `allow`: retained for documentation but not reported.

Prefer phrase matches before single-word matches.

### 2. Literal-claim check

For each suspected term, ask:

- Who or what acts?
- What exactly happens?
- What condition must be true?
- What changes, stops, breaks, passes, or fails?
- Which users, records, services, regions, files, or requests are affected?
- What evidence supports the judgment?
- How much, how often, or for how long?
- Could a reader test or verify the claim?

If the sentence cannot answer the relevant question, the jargon is probably hiding missing thought or missing evidence.

### 3. Metaphor check

Flag a metaphor when it performs the work of a specification.

Weak:

> The schema is the load-bearing seam in the system.

The sentence does not identify a dependency, interface, failure, or consequence.

Better:

> The importer and exporter both depend on the schema. A field rename breaks files written by older releases.

Use only facts present in the source. If the source does not provide the dependency or failure, state the gap instead of inventing one.

### 4. Verdict check

Flag words that declare a result without showing it.

Weak:

> The logs provide decisive proof that the retry path is healthy.

Ask:

- Which log entry?
- What does it show?
- Which retry case ran?
- What result would count as failure?

A supported revision may be:

> In all 50 test runs, the second request returned the stored result and created no duplicate row.

Do not add numbers or outcomes that the source does not supply.

### 5. Cluster check

One ordinary term may be harmless. A cluster often signals a borrowed register.

Review any short passage that combines several items such as:

> The load-bearing seam gates the handoff and keeps the blast radius clean.

Do not replace each word separately. Recover the literal claim first, then rewrite the sentence.

### 6. Voice check

Compare the term with the writer's supplied prose.

Flag it when:

- the writer never uses that register;
- it is more theatrical or corporate than the surrounding text;
- it makes a direct writer sound like a consultant;
- it makes a formal writer sound artificially casual;
- it replaces the writer's stable technical term with a fashionable synonym.

Preserve deliberate jokes, idioms, and professional vocabulary supported by the writer.

### 7. Repetition check

Count repeated watched terms and repeated semantic roles.

Examples:

- `gate`, `gated`, and `gating` count as one family;
- `scaffold`, `scaffolds`, and `scaffolding` count as one family;
- repeated words such as `clean`, `healthy`, and `authoritative` may all perform the same unsupported reassurance.

Do not vary terms merely to hide repetition. Replace them with the literal facts.

## Review score

Use this score when judgment is difficult.

| Signal | 0 | 1 | 2 |
|---|---|---|---|
| Literal meaning | exact | partly clear | unclear or metaphorical |
| Actor and action | explicit | one is implied | both are hidden |
| Scope or condition | exact | incomplete | absent |
| Evidence | shown or unnecessary | implied | unsupported verdict |
| Voice | natural | uncertain | mismatched |
| Repetition | isolated | repeated once | clustered or habitual |

Interpretation:

- `0-3`: usually keep;
- `4-6`: revise or define;
- `7-12`: rewrite from the literal claim.

An explicit house-style ban overrides the score.

## Rewrite method

Do not perform synonym replacement. Rebuild the sentence from its meaning.

### Pass 1: Preserve the record

Using the `human-writing` skill:

- identify facts that must not change;
- preserve uncertainty and qualifications;
- preserve the writer's stance and useful voice;
- retain exact technical nouns;
- do not invent evidence, examples, motives, or measurements.

Write a private one-sentence statement of what the source actually claims.

### Pass 2: Find the point

Using the `writing-well` skill:

- state the point before background;
- remove jargon used as camouflage;
- cut ceremonial wording and repeated conclusions;
- prefer the familiar word when it is equally exact;
- keep details that matter to the reader's decision.

### Pass 3: Repair the sentence

Using the `elements-of-style` skill:

- make the grammatical subject and main verb easy to find;
- turn hidden actions into verbs;
- keep modifiers near what they modify;
- state the condition before the consequence when that order helps;
- use stable terms for the same object;
- preserve defined or irreducible terminology.

### Pass 4: Make it concrete

Borrow only the relevant principles from `hemingway-prose`:

- use exact ordinary nouns;
- use active verbs when the actor matters;
- remove decorative metaphors and explanations already carried by facts;
- stop after the consequence is clear.

Do not apply fictional omission rules to technical, legal, academic, medical, or policy prose. Accuracy and explicit conditions come first.

### Pass 5: Check for substitution

Models often replace one watched term with another.

Reject revisions such as:

- `load-bearing` → `foundational`;
- `blast radius` → `impact footprint`;
- `gate` → `control point`;
- `spine` → `backbone`;
- `substrate` → `underlying layer`;
- `cleanly` → `seamlessly`;
- `decisive` → `definitive`.

The replacement must add literal meaning, not a fresher metaphor.

### Pass 6: Verify

Compare the revision with the source.

Confirm that it preserves:

- facts;
- names;
- numbers;
- chronology;
- causality;
- uncertainty;
- responsibility;
- technical distinctions;
- required terms;
- intended tone.

## Replacement questions

Use these questions instead of automatic substitutions.

| Watched term | Ask |
|---|---|
| `load-bearing` | What depends on it? What fails without it? |
| `blast radius` | Exactly what is affected, and what is not? |
| `footgun` | What mistake is easy to make? What happens next? |
| `yak shaving` | Which prerequisite task delays the main task? |
| `belt-and-suspenders` | What are the two independent safeguards? |
| `smoking gun` | Which piece of evidence shows the cause or event? |
| `spine` | What is the actual order, structure, or central argument? |
| `seam` | Which two components or responsibilities meet here? |
| `gate` | What exact condition must pass before what action? |
| `substrate` | Is this the operating system, runtime, database, network, file format, or something else? |
| `scaffold` | Is this temporary code, generated structure, setup work, or an example? |
| `wiring` | Which calls, imports, events, routes, or configuration entries connect the parts? |
| `handoff` | Who gives what to whom, and when does responsibility change? |
| `blocker` | Which unresolved fact or failed condition prevents the next action? |
| `drift` | Which values differ from which reference, by how much, and over what period? |
| `parity` | Which behaviors or measurements must match? |
| `clean` or `cleanly` | Does this mean correct, empty, formatted, passing, safe, quiet, or unchanged? |
| `healthy` | Which check passed, over what interval, and at what threshold? |
| `decisive`, `authoritative`, `proves` | What evidence supports that degree of certainty? |
| `landed`, `shipped` | Was it merged, deployed, released, enabled, delivered, or merely approved? |
| `surface` | Was it displayed, returned, discovered, reported, or made available? |

## Examples

The examples below are self-contained. Do not borrow their facts for other text.

### Dependency

Before:

> This helper is load-bearing because login and token refresh both call it.

After:

> Login and token refresh both call this helper. Removing it breaks both paths.

### Scope

Before:

> The feature flag limits the blast radius to beta users.

After:

> The feature flag keeps the change disabled for everyone except beta users.

### Misuse risk

Before:

> The optional account ID is a footgun: an empty value deletes the default account.

After:

> An empty account ID deletes the default account, so require an explicit ID before deletion.

### Approval condition

Before:

> The restore test is the final gate for deployment.

After:

> Deploy only after the restore test passes.

### Evidence

Before:

> The smoking gun is the 14:03 log line showing `account_id=null`.

After:

> At 14:03, the log records `account_id=null` immediately before the delete request.

### Status

Before:

> The fix landed cleanly in prod.

Possible revisions, depending on the source:

> The fix was deployed to production without an error.

> The fix was deployed to production, and the error rate did not increase during the next hour.

> The pull request was merged but has not been deployed.

Choose only the statement supported by the source.

### Exact technical term

Keep:

> The endpoint is idempotent: repeating the same request returns the stored result without creating another row.

`Idempotent` names a precise property and the sentence defines it.

### Literal use

Keep:

> The engineer replaced the load-bearing beam.

The phrase is literal.

### Deliberate voice

Possible keep:

> I spent the morning yak shaving so the test suite could run on my laptop.

Keep this only when the informal phrase belongs to the writer and suits the reader. In a formal report, name the prerequisite work.

## Discover new jargon

A static list will age. Use corpus evidence to propose new terms.

### Required material

Collect:

- a `model corpus`: outputs from the model or workflow under review;
- a `baseline corpus`: writing by the target writer, team, or comparable humans in the same domain;
- enough separate documents to distinguish a habit from one topic.

A same-domain baseline is more useful than general English. Code discussions should be compared with human code discussions, not novels or news.

### Discovery procedure

1. Remove code blocks, logs, identifiers, URLs, quoted source text, and generated tables when possible.
2. Extract one-, two-, and three-word phrases.
3. Count total frequency and document frequency.
4. Compare model frequency with baseline frequency using smoothing.
5. Group obvious inflections and spelling variants.
6. Exclude proper names, project names, commands, and required domain terms.
7. Read at least five examples of each high-ranking candidate.
8. Test the candidate for overloaded meaning, missing actors, vague scope, unsupported judgment, and voice mismatch.
9. Add it to the watchlist only when the contexts show a recurring style problem.
10. Record allowed uses and the question that recovers the literal claim.

The included `scripts/discover_jargon.py` ranks candidates. Its output is a review queue, not a ban list.

### Suggested admission rule

Add a new watch term when:

- it appears in at least three separate model documents;
- it is materially more common than in the baseline;
- most sampled uses fail at least two detection checks;
- a plain rewrite improves the sentence without losing a technical distinction.

Add a hard ban only when the house style requires one.

### Watchlist record

Each entry should contain:

```text
term:
match: word | phrase | regex
status: inspect | rewrite | ban | allow
category:
question:
allowed_when:
source:
first_seen:
notes:
```

Review the list periodically. Remove terms that no longer produce useful findings.

## Enforcement

Use three layers when strict compliance matters.

### Early instruction

Place the compact house rule in the earliest available style or system instruction:

> Prefer literal descriptions to stock engineering metaphors and insider slang. Do not use the current banned terms. Name the actor, action, condition, scope, evidence, and consequence.

An early rule helps drafting, but it does not replace editing.

### Context-sensitive edit

Apply this skill after the draft so legitimate technical terms survive and vague uses are rewritten.

### Mechanical check

Run:

```bash
python scripts/jargon_lint.py draft.md
```

The linter reports exact watchlist matches and can fail a build or hook. It cannot judge whether a technical term is correct; use the skill for that decision.

For a new corpus:

```bash
python scripts/discover_jargon.py \
  --model ./model-output \
  --baseline ./human-writing \
  --known references/watchlist.csv \
  --novel-only \
  --output candidates.csv
```

Review `candidates.csv` before updating the watchlist.

## Output behavior

### When revising

- Return the finished revision unless the user asks for notes.
- Preserve meaning, voice, uncertainty, and necessary terms.
- Do not announce each watched word.
- Do not replace jargon with longer bureaucratic prose.
- Do not add facts to make a vague sentence sound specific.

### When auditing

Report:

1. the term or phrase;
2. its location;
3. what it hides or leaves ambiguous;
4. the literal question the writer must answer;
5. the smallest useful repair;
6. any occurrence that should remain.

Order findings by effect on meaning, not alphabetically.

### When discovering

Return:

- ranked candidate terms;
- frequency in the model and baseline corpora;
- document count;
- sample contexts;
- likely category;
- recommendation: `ignore`, `inspect`, `rewrite`, or `ban`.

Do not claim the corpus was written by a model. State only that the terms are unusually frequent or repeatedly vague in the supplied material.

### When maintaining the list

- Preserve source and review notes.
- Add inflected forms only when matching cannot handle them safely.
- Record literal and technical exceptions.
- Prefer a small useful list to a large noisy one.

## Failure modes

Avoid these mistakes.

### Blind deletion

A blacklist removes exact technical language and can make prose less accurate.

### Jargon migration

The revision swaps one fashionable metaphor for another.

### Longer paraphrase

The edit expands a short vague phrase into a long vague phrase.

### Invented specificity

The editor adds systems, users, times, measurements, or causes not present in the source.

### Voice flattening

The editor removes a deliberate idiom or joke that belongs to the writer.

### False authorship claim

The editor treats a vocabulary pattern as proof that a model wrote the text.

### Baseline mismatch

The discovery process compares technical output with an unrelated general corpus and mistakes domain vocabulary for model jargon.

### Topic leakage

A word ranks highly because many documents discuss the same project, not because the model favors it.

### Single-word obsession

The editor counts words but misses repeated sentence shapes, metaphor clusters, and unsupported verdicts.

## Final check

Before delivering, ask:

- Did every retained technical term add exact meaning?
- Did every rewritten sentence name the relevant actor and action?
- Are conditions, scope, evidence, and consequences explicit where needed?
- Did any edit change the claim or certainty?
- Did the revision replace one stock phrase with another?
- Does the result sound like the writer rather than the editor?
- Can the reader understand the sentence on the first pass?
- Is the last sentence useful?

The governing test is simple:

> Say what happened, what it affects, and what follows.
