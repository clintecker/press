"""The import-time side-effect sandbox.

``press selftest`` proves that importing any distributable module loads
code, not does work: a module that connects to the network, spawns a
subprocess, or writes a file *while its body runs* is caught and named.
The trap cannot go through the process-runner adapter, because its whole
job is to intercept the *real* ``subprocess.Popen`` (and ``socket``, and
``open``) a hostile import would reach for -- so it lives here, in the one
package the boundary gate exempts, where a raw reference to those
primitives is legitimate.

``_import_sandbox`` monkeypatches the acting call (``connect``, ``Popen``,
``os.system``, ``Path.write_*``, and ``open`` in a write mode) for the
duration of a ``with`` block and restores every one afterward.
Constructing a socket or a ``Path`` is fine; *connecting* it, *running*
it, or *writing* through it is the side effect, so the guard sits on the
verb, not the object. ``press.selftest`` imports the context manager and
the exception from here.
"""

from __future__ import annotations

import contextlib
from pathlib import Path


class _ForbiddenImportSideEffect(Exception):
    """Raised by the import sandbox the instant a module, while being
    imported, reaches for the network, spawns a subprocess, or writes a
    file. Importing a runtime module must load code, not do work."""


@contextlib.contextmanager
def _import_sandbox():
    """Trap the forbidden import-time side effects for the duration of the
    block: a network connection, a spawned subprocess, or a filesystem
    write. Constructing a socket or a Path is fine; *connecting* it,
    *running* it, or *writing* through it is the side effect, so the guard
    sits on the acting call, not the object. Bytecode caching writes go
    through the import system's own low-level path (os.replace), not these
    Python-level APIs, so a normal import does not trip the guard."""

    import builtins
    import os
    import socket
    import subprocess

    write_modes = ("w", "a", "x", "+")
    real_open = builtins.open
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex
    real_create_connection = socket.create_connection
    real_popen_init = subprocess.Popen.__init__
    real_system = os.system
    real_write_text = Path.write_text
    real_write_bytes = Path.write_bytes

    def guard_open(file, mode="r", *args, **kwargs):
        if isinstance(mode, str) and any(flag in mode for flag in write_modes):
            raise _ForbiddenImportSideEffect(f"opened {file!r} for writing at import")
        return real_open(file, mode, *args, **kwargs)

    def guard_connect(self, address, *args, **kwargs):
        raise _ForbiddenImportSideEffect(f"opened a network connection to {address!r} at import")

    def guard_connect_ex(self, address, *args, **kwargs):
        raise _ForbiddenImportSideEffect(f"opened a network connection to {address!r} at import")

    def guard_create_connection(address, *args, **kwargs):
        raise _ForbiddenImportSideEffect(f"opened a network connection to {address!r} at import")

    def guard_popen(self, *args, **kwargs):
        command = args[0] if args else kwargs.get("args")
        raise _ForbiddenImportSideEffect(f"spawned a subprocess {command!r} at import")

    def guard_system(command):
        raise _ForbiddenImportSideEffect(f"ran a shell command {command!r} at import")

    def guard_write_text(self, *args, **kwargs):
        raise _ForbiddenImportSideEffect(f"wrote a file {str(self)!r} at import")

    def guard_write_bytes(self, *args, **kwargs):
        raise _ForbiddenImportSideEffect(f"wrote a file {str(self)!r} at import")

    builtins.open = guard_open
    socket.socket.connect = guard_connect
    socket.socket.connect_ex = guard_connect_ex
    socket.create_connection = guard_create_connection
    subprocess.Popen.__init__ = guard_popen
    os.system = guard_system
    Path.write_text = guard_write_text
    Path.write_bytes = guard_write_bytes
    try:
        yield
    finally:
        builtins.open = real_open
        socket.socket.connect = real_connect
        socket.socket.connect_ex = real_connect_ex
        socket.create_connection = real_create_connection
        subprocess.Popen.__init__ = real_popen_init
        os.system = real_system
        Path.write_text = real_write_text
        Path.write_bytes = real_write_bytes
