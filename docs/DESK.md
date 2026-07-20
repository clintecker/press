# The operator desk

`press desk` is an optional terminal interface over the press command
line. It makes a book repository easier to observe and drive; it is not
a second publishing engine. Everything it shows comes from the same
registries the CLI uses, and every action it runs is a `press` child,
so the desk cannot bless a stale artifact, misname a command, or
disagree with the command line. Uninstall the extra and a complete
command-line workflow remains.

## Installing and running

The desk ships behind an optional extra so a bare install builds books
without it:

```sh
pip install 'press[tui]'
press desk        # from inside a book repository
```

Run without the extra and `press desk` says so and exits; run it where
there is no terminal and it points you back at the CLI. It never draws
into a pipe.

## What the desk shows

The home screen (DESK) is the read model, rendered:

- The book's identity: title, authors, trim, and slug, from the typed
  book model.
- Every artifact the registry declares, each with its evidence state.
- The toolchain readiness, from `press doctor`'s findings; when a
  required tool is missing the desk says which and grays out the
  actions that need it.

## The evidence language

Artifact state comes from content digests and recorded verification,
never a timestamp. A file touched but unchanged is not stale, and a
rebuild to identical bytes is not new work. The five states:

| glyph | state | meaning |
|---|---|---|
| `-` | not built | the artifact's output does not exist |
| `o` | present, unverified | it exists, but no evidence records a verified digest |
| `*` | verified | its current digest matches the digest that was verified |
| `!` | changed since proof | it exists but its bytes differ from the verified digest |
| `/` | incomplete | some of a multi-output artifact's outputs are missing |

## Keymap

| key | action |
|---|---|
| `p` | open the target picker and run a target |
| `w` | open the setup wizard (guided book configuration) |
| `r` | refresh the model (never caches a fact a rebuild would change) |
| `q` | quit |
| `escape` | leave a run, the picker, or the wizard, back to DESK |

The picker is generated from the one command catalog, so it offers
exactly the commands the CLI runs. Selecting one opens a RUN view that
streams the child's output and shows its exact verdict: a nonzero or
cancelled run reports its precise exit code, because the return code is
the verdict, never re-derived from the output.

## The setup wizard

`w` opens a guided flow for a book's identity, pre-filled with the current
values and their help. Every read and write goes through the same typed
configuration boundary as `press config` (the #155 door), so the wizard
validates and preserves a book's YAML exactly as CLI automation does. An
edit is collected in memory and shown as an exact diff with the real
validator's verdict before a byte is written; `Ctrl+R` reviews, `Ctrl+A`
applies a clean preview, and cancel, back, or a validation failure leaves
the file unchanged. A secret-looking value is refused before it can reach
the config, and a completed wizard hands back a runnable next step
(`press check`), never a claim that the book is ready.

## The CLI escape hatch

The desk is a convenience, not a dependency. Every action it runs is a
`press <target>` you can type yourself; the RUN view even prints the
exact command it launched. If the desk is ever in doubt, the command
line is the ground truth, and the desk is deliberately thin over it.
