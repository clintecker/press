# What a receiver actually does

A receiver hears everything and must be taught to ignore almost all of it.
The air at any moment carries broadcast, aviation, weather, the switching
supply in the next room, and the sun. The work of a receiver is not to
find a station; it is to reject the rest of the band well enough that one
station is left standing.

That rejection happens in stages, and each stage costs something. A sharp
filter early in the chain protects everything after it, but a filter is
never free: it removes some of the wanted signal along with the unwanted,
and it adds noise of its own.

## The chain, front to back

Every small receiver has the same order, whatever its age:

| Stage | What it does | What it costs |
|---|---|---|
| Antenna | Turns a field into a voltage | Nothing, if matched |
| Preselector | Removes far-off frequencies | A little wanted signal |
| Amplifier | Raises the level | Adds its own noise |
| Mixer | Shifts the frequency down | Distortion if overdriven |
| Filter | Removes the neighbours | Ringing, if too sharp |
| Detector | Recovers the audio | Depends on the mode |

The order matters more than the quality of any one part. An excellent
amplifier placed after a poor mixer amplifies a signal that has already
been spoiled.

## Impedance, and why it is not optional

An antenna delivers power to the receiver only when the two agree about
impedance. A quarter-wave wire against a good ground plane presents
roughly 36 ohms; most receivers expect 50. That mismatch alone is minor.
A random length of wire clipped to a terminal may present several hundred
ohms at one frequency and a few at another, and the receiver's response
will rise and fall across the band for reasons that have nothing to do
with the stations.[^match]

[^match]: A simple resistive pad will hide a mismatch by throwing away
power in both directions. It is a legitimate repair when the alternative
is an unstable amplifier, but it is attenuation, not a match.

Attenuation is the honest instrument here. A switchable pad of 10 dB in
front of the receiver tells you immediately whether a problem is coming
from outside or from within: if the interference falls by 10 dB along
with the station, it arrived through the antenna; if it does not move,
it is being made inside the case.
