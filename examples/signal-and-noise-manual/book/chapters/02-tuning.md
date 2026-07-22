# Tuning by measurement

Measure twice, because the meter is cheaper than the part. A tuned circuit
that is adjusted by ear will land somewhere near correct and stay there for
years, quietly costing a few decibels. A tuned circuit adjusted against a
meter lands where the design intended.

## The three numbers

Almost every alignment reduces to three readings taken in order.

| Reading | Instrument | Typical target |
|---|---|---|
| Supply voltage | Meter, at the regulator output | Within 5% of stated |
| Oscillator frequency | Counter, at the buffer | Within 100 Hz at band edge |
| Recovered audio | Meter, across the load | Peak, with input held constant |

Take them in that order every time. An oscillator that reads low because
its supply is low will be adjusted onto the correct frequency at the wrong
voltage, and will move again the moment the battery recovers.

## What a capacitor is doing while you turn it

A variable capacitor changes the resonant frequency of the circuit it sits
in, but it also changes the loaded quality factor, and therefore the
bandwidth. Tuning for maximum output at one setting can leave the circuit
broader than intended, which is why a stage that peaks beautifully on a
strong local station may be unusable next to a stronger neighbour.

When a peak is broad and indistinct, suspect a resistive loss rather than
the capacitor: a leaking coupling capacitor, a corroded ground return, or
a coil whose former has absorbed damp. Each one lowers the quality factor
and flattens the peak in exactly the same way.

## Drift, and how to tell its source

Frequency drift has three usual causes, and they are distinguishable by
their timing:

- Warm-up drift settles within minutes and then stops.
- Supply drift follows the battery and reverses when charged.
- Thermal drift follows the room and reverses overnight.

A frequency that moves and never returns is not drift. It is a component
changing value, and it will keep going.
