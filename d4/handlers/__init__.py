"""
D⁴ event handlers — each module registers itself via @event_handler.

Importing this package registers all built-in handlers with System 1's
dispatch registry.  New domain teams extend the grammar by adding a
module here — no changes to the core.
"""

from . import validate, lookup, mutate, notify
