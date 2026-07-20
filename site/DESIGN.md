# press — documentation site design system

A fresh, serious direction for the *press* docs: **cool graphite paper, one warm cinnabar ink.**
Serious developer-tooling documentation — calm, dense, fast to scan, print-literate. The site is
*read*, not admired; reference-reading and navigation come first.

This system is expressed as **one stylesheet** (`site/press.css`) over the **fixed, pandoc-generated
DOM** plus vendored `woff2` fonts. Its only script is a small
progressive-enhancement copy-button helper (`copy.js`) — the page works fully
without it and asks nothing of third parties; everything else, including the
mobile menu, is pure CSS. It is **theme-aware** (light + dark via
`prefers-color-scheme`), and makes **no third-party requests**. The canvas preview
(`Press Docs Design System.dc.html`) shows every component in both themes; this document is the
authority for `/design-sync`.

---

## 1 · Visual theme & density

**Idiom.** A screen-native, tooling-serious ground of *cool* neutrals (a hair of blue in the grays,
not the current warm cream), carrying a single **warm cinnabar** as the "second ink" — the letterpress
concept, modernised. The tension of a warm accent on a cool ground is the whole identity: quiet,
deliberate, unmistakably *designed* without decoration.

**Why cool, not warm.** Warm paper reads "book/letterpress"; the brief wants "serious developer-tooling
docs, Stripe/Tailwind-caliber." Cool graphite is more screen-native and disappears behind the text.
The one warm ink keeps the press's soul and does all the identity work, so nothing else has to.

**Density.** Reference docs, not an essay. Reading measure **42rem**; body scales from
~17px on a phone to ~34px on a wide desktop (a fluid root, line-height 1.62); headings
tight; generous-but-compact vertical rhythm on a 4px grid. Tables and code get a wider measure and
sit at comfortable-but-dense padding.

**Flatness.** Print-literate and flat: hairline rules and two ambient surfaces do the structural work.
No cards-with-shadows in the *content*; elevation is reserved for the (nonexistent) — see §6.

---

## 2 · Color palette & semantic roles

Ten semantic tokens. Two ambient surfaces (`--paper`, `--surface`) — that's the whole depth budget.
Everything is a CSS custom property so the whole system re-themes from one `:root` block.

```css
:root {                          /* ── Light · prefers-color-scheme: light ── */
  --paper:        #FAFAFB;   /* page background — cool near-white, recedes         */
  --surface:      #F2F3F6;   /* code, callouts, field tables — 1 step off paper    */
  --zebra:        #F6F7F9;   /* alternate table rows — barely-there banding        */
  --ink:          #1B1D22;   /* body text — cool near-black (16.2:1 on paper)       */
  --muted:        #565C66;   /* secondary text, labels, nav rest (6.5:1)           */
  --accent:       #D64A2A;   /* THE mark, rules, current-page — non-text/large use */
  --accent-ink:   #B23A1E;   /* links & emphasis TEXT — deeper, AA at body size    */
  --rule:         #E5E7EC;   /* hairlines, borders, dividers                       */
  --rule-strong:  #CCD0D8;   /* table-head underline, record separators            */
  --code-ink:     #33373F;   /* code text — softer than body, calm on surface      */
}

@media (prefers-color-scheme: dark) {
  :root {                        /* ── Dark · prefers-color-scheme: dark ── */
    --paper:       #17191D;  /* graphite, not black — kinder for long reads (14.6:1)*/
    --surface:     #1E2126;  /* raised code/field surface                          */
    --zebra:       #1B1E22;  /* alternate rows                                     */
    --ink:         #E8EAEE;  /* body text — cool off-white                         */
    --muted:       #98A0AB;  /* secondary (6.7:1)                                  */
    --accent:      #F0774E;  /* cinnabar, brightened so it glows on graphite       */
    --accent-ink:  #F0774E;  /* on dark the bright cinnabar already clears AA (6.3) */
    --rule:        #2A2E34;  /* hairlines                                          */
    --rule-strong: #3B4048;  /* stronger dividers                                  */
    --code-ink:    #D7DBE1;  /* code text                                          */
  }
}
```

**Two-ink rule.** In the chrome and prose, `--accent` is one restrained hue. Use it for: the
wordmark `.mark` dot, the current-page tick, `blockquote`/record left-rules, list `::marker`s,
and focus rings. Use `--accent-ink` (a deeper cut) for **link and emphasis text** so it clears
AA at body size. Do not introduce a second accent hue in the chrome or prose (no separate "link
blue"); calm comes from restraint. The one deliberate exception is code: syntax highlighting
carries its own small, quiet palette (see Code below).

**Contrast — WCAG AA verified** (WCAG 2 relative-luminance; AAA is ≥7:1, AA ≥4.5:1):

| Theme | Pairing | Ratio | Level |
|---|---|--:|:--|
| Light | body — `--ink` on `--paper` | 16.2 | AAA |
| Light | secondary — `--muted` on `--paper` | 6.5 | AAA |
| Light | links — `--accent-ink` on `--paper` | 5.7 | AA |
| Light | code — `--code-ink` on `--surface` | 10.8 | AAA |
| Light | UI accent — `--accent` on `--paper` | 4.1 | AA * |
| Dark | body — `--ink` on `--paper` | 14.6 | AAA |
| Dark | secondary — `--muted` on `--paper` | 6.7 | AAA |
| Dark | links — `--accent-ink` on `--paper` | 6.3 | AA |
| Dark | code — `--code-ink` on `--surface` | 11.6 | AAA |

\* `--accent` is used only as **non-text / large UI** (the mark, rules, the ≥2px current-page
underline), where the AA threshold is 3:1. Body-size accent *text* always uses `--accent-ink`.

---

## 3 · Typography

Same proven docs structure as today (serif prose · sans chrome & headings · mono code), a wholly new
voice. All three are open (OFL) and **self-hostable as `woff2`**.

| Role | Family | Rationale |
|---|---|---|
| Prose / reading | **Literata** | Engineered for long-form screen reading (optical sizes); warm, sturdy at small sizes and in dark mode. Carries the "typographic taste" the brief wants. |
| Chrome / headings / labels | **Hanken Grotesk** | Warm neo-grotesque, excellent at 11–14px for dense nav, table heads, and small-caps labels; more humane than a cold geometric, more serious than a friendly rounded. |
| Code / data | **JetBrains Mono** | Terminal-native, superb metrics, clear at 13px, tabular figures for aligned numerics. |

**Vendor** (`site/fonts/`, all OFL): Literata 400 / 600 / 700 + 400 italic · Hanken Grotesk 400 / 500 /
600 / 700 / 800 · JetBrains Mono 400 / 500 / 600. Subset to Latin. *No Google Fonts, no CDN* — the
canvas preview uses a web-font CDN for iteration only.

**Type scale** — rem-based over a fluid root (`html` font-size
`clamp(17px, 1.3vw + 9px, 34px)`), so the whole document grows on wide
viewports; the chrome uses a gentler `--ui` scale so the sidebar stays
sane. The px figures below are the mobile/base rendering:

| Element | Family / weight | Size / line-height | Notes |
|---|---|---|---|
| `h1` | Hanken 800 | 33px / 1.14, `-0.022em` | page title; no rule above |
| `h2` | Hanken 700 | 23px / 1.20, `-0.012em` | **top hairline** — signals a new section at a glance |
| `h3` | Hanken 700 | 18px / 1.3 | subsection |
| `h4` | Hanken 700 | 12.5px / 1.3, **uppercase**, `0.08em` | label-grade heading |
| body `p` | Literata 400 | 17px / 1.62 (base) | reading measure 42rem |
| small / UI | Hanken 500 | 13.5–14px | nav, footer, captions |
| block code | JetBrains 400 | 13.5px / 1.6 | |
| inline code | JetBrains 400 | 0.85em | chip, see §4 |

**Depth cue.** `h1` is heaviest and unruled; `h2` earns a full-width top hairline; `h3` is unruled and
lighter; `h4` drops to uppercase label grade. You can read the outline depth from weight + rule alone.

---

## 4 · Components & states

### Toolbar & grouped nav  (`header.toolbar`)

- Sticky, `--paper` background, single `--rule` bottom hairline. Wordmark left, grouped nav right.
- `.wordmark` — Hanken 800, `-0.03em`, `--ink`; `.mark` is a cinnabar full-stop (`press.`) — the
  quiet, distinctive identity mark. No logo image needed.
- **Groups are visually distinct**: each `.nav-group` leads with a `.nav-group-label`
  (Hanken 700, 10.5px, uppercase, `0.11em`, `--muted`) — *Guide / Reference / Project* — and groups
  are separated by a `--rule` left divider. This fixes "groups blur together."
- **Current page is obvious**: `--ink` + weight 700 + a 2px `--accent` bottom-border. Rest links are
  `--muted`→`--ink`, hover `--accent-ink`.
- `.repo` ("source ↗") sits last behind a divider, `--muted`.
- **Mobile (< 760px): CSS-only menu.** A visually-hidden `#nav-toggle` checkbox + `.nav-burger`
  label; `#nav-toggle:checked ~ nav` reveals a stacked panel. Focus-safe, no JS.

### Links (prose)  `a`

- `--accent-ink`, `underline`, `text-underline-offset:2px`, `1px` thickness → thickens to `2px` on
  hover/focus. Always underlined (never color-only) for accessibility.

### Code  `pre > code`, inline `code`

- **Block**: `--surface` panel, `1px --rule` border, `9px` radius, `16–18px` padding, `overflow-x:auto`.
  JetBrains, ~0.84rem/1.6. Pandoc emits skylighting token classes, which
  press.css colors with a quiet, theme-aware palette (comments recede in
  italic via `--hl-comment`, strings `--hl-string`, keywords `--hl-keyword`,
  numbers `--hl-number`, command and function names take the accent,
  attributes `--hl-attr`); un-tokenized text stays `--code-ink`, so plain
  and console blocks read cleanly. A copy button (the one script) sits at
  the block corner. Colors stay theme-owned in the stylesheet.
- **Inline**: a *chip* — `--surface` fill, `1px --rule` border, `4px` radius, `1px 5px` padding,
  `0.85em`. Panel-vs-chip is the clear block/inline distinction the brief asked for.

### Tables  `table > thead/tbody/tr/th/td`

- Calm, scannable: `th` is Hanken 700, 11px, uppercase `0.06em`, `--muted`, with a **2px `--rule-strong`
  underline**. `td` rows separated by `1px --rule` hairlines, with a **whisper of `--zebra`** on even
  rows for eye-tracking.
- **Numerics** right-align + `tabular-nums`, driven by pandoc's per-column alignment
  (`[style*="text-align:right"]`).
- **Wide tables scroll** without a wrapper: `table{ display:block; overflow-x:auto }` (browsers keep
  column alignment via an anonymous table box). Tables get the wider measure.

### Reference record cards  (`body.doc-entries`)

- The content DOM is flat (no per-record wrapper), so a record is carded by **rhythm, not a box**:
  each record's `h3` (name) gets a `--rule-strong` top rule + top padding; the first `p` after it is
  the **id · criticality** subtitle (mono, `--muted`, with the id in a cinnabar chip); the next `p`
  is the statement (serif lead); the labelled fields render as a compact **spec box** — a bordered,
  radius-9 table with `--surface` label column (Hanken 600 `--muted`) and mono values.
- Stays legible at length: strong separators + generous spacing between records.

### Footer  (`footer.colophon`)

- Top `--rule` hairline; `--muted`. `nav[aria-label="Policies"]` links left (hover `--accent-ink`);
  `.stamp` right, mono 12.5px, with the `<sha>` in `--accent-ink`.

---

## 5 · Layout & spacing

- **Spacing scale (4px base):** `4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 48 · 64`. Use tokens, not
  ad-hoc values.
- **Reading column.** Per the fixed model, the column is created on direct body children:
  `body > *:not(.toolbar):not(.colophon):not(table):not(pre)` gets `max-width` + `margin-inline:auto`.
  `table` and `pre` get a **wider** max so dense data breathes.
- **Measures:** prose `--measure: 42rem`; wide (table/pre) `--measure-wide: 54rem` (rem, not
  ch, so every element shares one column regardless of its font size); page gutters
  `clamp(20px, 5vw, 40px)`.
- **Vertical rhythm:** `p` margin `0 0 0.9em`; `h2` `2rem` top / `0.55rem` bottom; `h3` `1.6rem` /
  `0.45rem`; lists `0 0 1rem` with `1.35rem` indent.

## 6 · Depth & elevation

Deliberately near-zero — this is flat, print-literate docs.
- **Content:** no shadows. Structure = hairlines (`--rule`), the two surfaces, and the accent.
- **Only exception:** the mobile menu panel may take a single soft shadow to read as an overlay.
- Radii: `4px` (chips) · `9px` (code/field panels). Nothing pill-shaped in content.

## 7 · Do's & don'ts

**Do**
- Let hairlines and the two surfaces carry structure; keep it flat.
- Reserve the accent; one or two accent moments per screen is plenty.
- Right-align + `tabular-nums` every numeric column.
- Keep the reading measure tight; give tables/code the wide measure.
- Verify AA on **both** themes for any new text color.

**Don't**
- No second accent hue in the chrome or prose (the code-highlighting palette
  is the one deliberate exception), no gradients, no decorative flourish.
- No color-only links (always underline); no accent *text* below large sizes (use `--accent-ink`).
- No shadows on content cards; no rounded-container-with-left-accent tropes.
- No external requests and no web fonts — self-host only. The only script is
  the inline copy helper; keep everything else pure CSS (the mobile menu
  stays `:checked`), and let the page work fully with JS disabled.
- Don't wrap or restructure pandoc content; style the flat DOM (see §9).

## 8 · Responsive behavior & breakpoints

- **Mobile-first.** Single column always; the reading measure caps width on large screens.
- **`< 760px`:** desktop nav hides; `.nav-burger` appears; `#nav-toggle:checked ~ nav` opens the
  stacked panel. Footer stacks. Gutters shrink via `clamp`.
- **`≥ 760px`:** grouped nav inline with dividers; footer is a space-between row.
- Tables/code always `overflow-x:auto` so narrow screens scroll a wide table instead of breaking it.
- Honor `prefers-reduced-motion: reduce` — drop the underline/hover transitions.

## 9 · Agent prompt guide

> **Constraints (hard):** static, **CSS-first** — the only script is the
> progressive-enhancement copy helper and the page must work fully without it
> (mobile menu stays CSS `:checked`); **self-host fonts**
> as `woff2` in `site/fonts/`, zero third-party requests; **theme-aware** via `prefers-color-scheme`,
> both first-class, AA on both; **fixed pandoc DOM** — content elements are **direct children of
> `<body>`** (`h1`–`h4`, `p`, `ul/ol/li`, `pre>code`, inline `code`, `table…`, `blockquote`, `a`,
> `hr`, `strong/em`); no content wrappers. The reading column is a `max-width` on
> `body > *:not(.toolbar):not(.colophon):not(table):not(pre)`.
>
> **Shell (only place you may edit markup):** `scripts/build_site.py` renders the `header.toolbar` and
> `footer.colophon` and may set a **per-page `<body>` class** (`home`, `doc-entries`, …). Keep the
> classes in "The chrome's DOM" below.
>
> **When adding a screen:** compose from existing element rules; reach for a new token only if none
> fits, and add it to **both** `:root` blocks with a rationale + a verified contrast ratio. Prefer
> hairlines and the two surfaces over new colors. One accent, restrained. Match the existing density
> and type scale.

### The chrome's DOM (style these exactly)

```text
header.toolbar
  a.wordmark            → "press" + span.mark (cinnabar dot)
  input#nav-toggle.nav-toggle + label.nav-burger      (CSS-only menu)
  nav[aria-label="Site"]
    span.nav-group → span.nav-group-label + a a a …    (Guide / Reference / Project)
    a.repo         → "source ↗"
… pandoc content (direct body children) …
footer.colophon
  nav[aria-label="Policies"] → a a a
  p.stamp                    → "built from <sha> (date); regenerated on every push"
```

---

## The authoritative stylesheet

`site/press.css` is the single source of truth for the implemented system;
this document is the design rationale behind it. When they disagree, the
stylesheet wins — update this doc to match, not the reverse.

### Adaptations made when implementing against the real DOM

Two component specs above assumed a DOM shape the generated pages don't
have; the stylesheet targets the real one:

- **Reference records are `h2`, not `h3`.** The invariants and providers
  pages emit `##` per record, so the record-card rules in §4 target
  `body.doc-entries h2` (+ its subtitle `h2 + p`), not `h3`.
- **The landing has no eyebrow.** The README opens with `# press` and a
  description paragraph, so `body.home` styles the first paragraph as the
  lead; there is no uppercase eyebrow line.

Fonts are self-hosted OFL `woff2` in `site/fonts/` (Literata, Hanken
Grotesk, JetBrains Mono; Latin subset). The build shell in
`scripts/build_site.py` sets the per-page `<body>` class (`home`,
`doc-entries`) and renders the toolbar and colophon.
