"""Allow `python3 -m sessionwiki` to invoke the CLI."""
from sessionwiki.cli import main
import sys

if __name__ == "__main__":
    sys.exit(main())
