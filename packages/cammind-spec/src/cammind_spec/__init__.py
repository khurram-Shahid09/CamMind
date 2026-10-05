"""The rule spec: the contract between the plain-English sentence and the rule engine.

The compiler (services/core) produces it, the user confirms it, and the engine
(services/vision) runs it. Models arrive with the engine (docs/15, day 5).
"""

SPEC_VERSION = 1

__all__ = ["SPEC_VERSION"]
