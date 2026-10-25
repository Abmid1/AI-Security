"""Modular security-scanner framework (Milestone 2).

Each scanner is wrapped by an adapter implementing the ScannerAdapter interface
in base.py. Adapters are registered in registry.py. Results are normalized into
one canonical finding format by normalize.py.

Design goals:
- Replaceable: add or swap a scanner by writing one adapter; nothing else changes.
- Honest: a missing tool becomes a recorded "skipped area", never a silent gap.
- Safe: dynamic (network) scanning requires explicit authorization and scope.
"""
