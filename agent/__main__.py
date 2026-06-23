"""Allow `python -m agent.eval` (eval is the primary CLI entry)."""

from agent.eval import main

if __name__ == "__main__":
    raise SystemExit(main())
