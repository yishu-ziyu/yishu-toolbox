"""让 `python -m ticket` 工作"""
from ticket.cli import main
import sys

if __name__ == "__main__":
    sys.exit(main())
