# Repair away from the bench

Field repair is triage. The aim is not to restore the equipment to its
original condition; it is to get it working well enough to finish the
task, without making the eventual proper repair harder.

## Order of suspicion

Work from the most likely and cheapest to check:

1. Power. Connectors, fuse, battery under load rather than at rest.
2. Connections. Anything that was moved, flexed, or rained on.
3. Passives that fail open or leaky: electrolytics first.
4. Semiconductors, last, because they mostly fail for a reason.

Skipping to step four is the common error. A transistor replaced because
of a bad ground will fail again within the hour, and the second failure
will be blamed on the replacement part.

## Solder in the cold

Cold hands and cold work make cold joints. Warm the board, not just the
iron, and give the joint a full second after the solder flows before
letting it move. A joint that looks grey and grainy has moved while
setting and should be reflowed rather than reinforced.

Keep a short length of desoldering braid and a small tin of flux; nearly
every field repair that goes wrong goes wrong during removal, not during
fitting.

## The ferrite trick

When a receiver picks up its own supply, a ferrite clamped over the lead
near the case will often remove it entirely. This works because the
ferrite raises the impedance of the common-mode path without affecting
the differential current the circuit actually uses.

```text
        supply lead
   ----[ ferrite ]------> to receiver
        clamp within 50 mm of the case
```

If the interference falls but does not disappear, add a second clamp
rather than a larger one; two spaced along the lead outperform one heavy
sleeve at the same total mass.

## What to write down

Record the reading, not the conclusion. "Supply 11.4 V under load, drops
to 9.1 V on transmit" survives being read six months later. "Battery
weak" does not, because it does not say how weak, under what load, or
whether it recovered.
