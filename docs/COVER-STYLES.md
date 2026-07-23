# Cover styles

A cover **style** is an art-direction template — a layout, a typographic idiom,
and rules for imagery — that the press fills with one book's title, author,
palette, and subject. The house library spans the history of the form, from the
1935 Penguin grid to contemporary collage. Every cover below is the **same
book** — *Between the Tides*, in the same teal palette — asked for in a
different style. One field in your config chooses which.

<!--COVER-STYLES-->

## Choosing a style

Name a style and a subject in `config/aesthetic.yaml`:

```yaml
cover:
  style: penguin-tri-band
  subject: "a rocky intertidal shore at low tide, tide pools, kelp, a shorebird"
```

Then commission the art:

```sh
press cover                 # uses the style and subject above
press cover --style art-deco    # override for a one-off
press cover --list              # every style, with a one-line note
```

`press cover` writes the art to `build/cover/` and prints the one command that
installs it — `press art accept build/cover/cover.png --as cover` — the same
intake every commissioned cover passes through, which enforces the cover
geometry and writes `assets/cover.jpg`. With no image-model key set, `press
cover` prints the ready-to-run prompt instead, so the same styles drive a
manual or agent-run commission and the press stays offline by default.

## Building your own

The house set is a starting point, not a fence. Add `config/cover-styles.yaml`
to your book with the same shape, and your styles merge over the built-ins:

```yaml
styles:
  my-house-style:
    name: "My house style"
    era: "your imprint"
    note: "what it looks like, in a line"
    text: baked            # the model letters the title; use `composited`
                           # to leave the art clear and have the press set type
    prompt: |
      A book cover, portrait, on {paper}. ...describe the layout, imagery, and
      typography... The title "{title}" and author "{author}" set ...
```

Your template may use `{title}`, `{author}`, `{imprint}`, `{initials}`,
`{subject}`, `{accent}`, and `{paper}`, each filled from your book's config.
Then `press cover --style my-house-style`. Nothing about the house library is
privileged; your book's styles are first-class.
