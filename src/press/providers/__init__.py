"""Provider-neutral print fulfillment.

A book site initiates a print order; a provider prints and ships it.
Coupling the domain to one provider's SDK would make the first provider a
permanent architecture and tempt false common-denominator behavior when
the next provider lacks cancellation, webhooks, or file validation. So
the domain speaks one typed contract (:mod:`press.providers.contract`);
each provider is an adapter that maps its own vocabulary to it and
declares, honestly, which capabilities it does not support. A stateful
smart fake (:mod:`press.providers.fake`) and a shared conformance suite
prove every adapter behaves; the Lulu adapter
(:mod:`press.providers.lulu`) is the first real one.

Adapters never open a socket themselves: HTTP is an injected transport,
so the boundary layer owns the real network calls and a test drives a
canned one. Raw provider strings and SDK types stop at the adapter.
"""

from __future__ import annotations

from . import contract

__all__ = ["contract"]
