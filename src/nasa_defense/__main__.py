from __future__ import annotations

import sys

from . import config, watch


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    dry_run = "--dry-run" in argv

    sink = None
    if not dry_run:
        from .sinks.github_issues import GitHubIssues
        sink = GitHubIssues.from_env()

    try:
        events = watch.run(state_dir=config.STATE_DIR, sink=sink, dry_run=dry_run)
    except Exception as exc:  # surface red in Actions; state not advanced
        print(f"run failed: {exc}", file=sys.stderr)
        return 1

    print(f"emitted {len(events)} event(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
