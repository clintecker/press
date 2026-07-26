# Plates and placement

A manual lives or dies by its figures, and the press places them by *intent*,
not by inches. You never write a width in points or a side as "left"; you name
where a figure sits against the measure and against the page's binding, and the
house does the geometry -- so a figure that hangs on the binding side stays on
the binding side whether it falls on a recto or a verso. Here is one schematic,
the crystal set from Chapter 1, laid every way the vocabulary allows. Each
caption is set as the placement produced it.

## Inline, at the full measure

The plainest placement runs the figure in the text column at the full width of
the measure -- `place=inline width=full-measure`. It breaks the flow, centred,
its caption beneath, which is what a bare `![caption](image)` already does; the
vocabulary only makes it explicit.

![Inline, at the full measure.](assets/woodcuts/crystal-set.png){.figure width=full-measure place=inline fig-alt="A crystal radio set: a long-wire antenna and a ground, a tuning coil, a variable capacitor, a cat's-whisker crystal detector, and a pair of headphones, drawn as a spare schematic."}

## Wrapped on the inner side

![Wrapped, inner side.](assets/woodcuts/crystal-set.png){.figure width=half-measure place=wrap-inner outset=1em fig-alt="The same crystal-set schematic, set at half the measure."}

Set smaller -- a half or a third of the measure -- a figure can let the text
run around it. `place=wrap-inner` holds it on the binding side, and `outset`
sets the gap the running text keeps from it. The paragraph beside a wrapped
figure wants enough length to close beneath it, or the next heading rides up
into the runaround; a manual page usually has the words to spare, as this one
does, describing the set at some length so the coil and the detector both have
prose to sit against while the reader's eye falls down the column and back to
the diagram again.

## Wrapped on the outer side

![Wrapped, outer side.](assets/woodcuts/crystal-set.png){.figure width=half-measure place=wrap-outer outset=1em fig-alt="The crystal-set schematic wrapped toward the outer margin."}

`place=wrap-outer` is the mirror: the figure hangs toward the outer edge of the
page, the running text filling the binding side. On a verso this puts the
diagram to the left; on a recto, to the right -- the press works that out from
the page number, so you never have to. Again the surrounding paragraph carries
enough text to wrap the figure and close under it, which on a field manual is
no hardship, since there is always one more thing to say about keeping a
receiver alive in the weather: dry the coil, tin the joints, and hold the
crystal's whisker light on its facet.

## As a plate

`place=plate` is the literary woodcut idiom: an unnumbered figure, pinned where
you place it, with a quiet italic caption and no "Figure N." A bare image with
no declared kind is a plate too, so this is the house default for a picture
that is illustration rather than reference.

![A plate: unnumbered, pinned in place.](assets/woodcuts/crystal-set.png){.plate place=plate}

## Full bleed

`place=full-bleed` gives the figure its own leaf and fills it. Use it for a
schematic a reader will want to lay flat on the bench beside the work.

![Full bleed: the figure takes its own page.](assets/woodcuts/crystal-set.png){.figure place=full-bleed fig-alt="The crystal-set schematic filling its own page."}

## Frontispiece

`place=frontispiece` faces the opening of the next chapter -- the plate on the
verso, the chapter head on the recto across the gutter.

![Frontispiece, facing the next chapter opening.](assets/woodcuts/crystal-set.png){.figure place=frontispiece fig-alt="The crystal-set schematic as a frontispiece facing the next chapter."}
