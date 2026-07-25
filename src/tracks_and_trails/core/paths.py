"""Platform directories, output-template rendering, and filename sanitizing.

Enforces the intersection of Linux and Windows filesystem rules, and guarantees a
rendered template cannot escape the configured output directory (ARCHITECTURE.md §8)."""
