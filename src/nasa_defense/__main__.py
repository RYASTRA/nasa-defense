from __future__ import annotations

import os
import sys

from . import config, watch


def main(argv: list[str] | None = None) -> int:
    config.load_dotenv()
    if not os.environ.get("NASA_API_KEY"):
        print(
            "error: NASA_API_KEY is required. Add it to .env (see .env.example), "
            "or set it in the environment / GitHub Actions secrets.",
            file=sys.stderr,
        )
        return 1
    argv = sys.argv[1:] if argv is None else argv
    dry_run = "--dry-run" in argv

    sink = None
    if not dry_run:
        from .sinks.github_issues import GitHubIssues  # pylint: disable=import-outside-toplevel

        sink = GitHubIssues.from_env()

    try:
        events = watch.run(state_dir=config.STATE_DIR, sink=sink, dry_run=dry_run)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # surface red in Actions; state not advanced
        print(f"run failed: {exc}", file=sys.stderr)
        return 1

    print(f"emitted {len(events)} event(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
