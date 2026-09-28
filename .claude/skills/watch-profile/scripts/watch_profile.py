#!/usr/bin/env python3
"""Watch every video on a creator profile or playlist (TikTok, YouTube, ...).

Lists the profile's videos with yt-dlp, then runs the watch skill's watch.py on
each one and writes a combined Markdown report.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WATCH_PY = Path(__file__).resolve().parents[2] / "watch" / "scripts" / "watch.py"
BLOCK_HINTS = ("Tunnel connection failed: 403", "Unable to connect to proxy", "CONNECT tunnel failed")


def list_videos(url: str, limit: int) -> list[dict]:
    cmd = ["yt-dlp", "--flat-playlist", "--dump-json", "--playlist-end", str(limit), url]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    videos = []
    for line in proc.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        link = item.get("webpage_url") or item.get("url")
        if link:
            videos.append({"url": link, "title": item.get("title") or item.get("id") or link,
                           "duration": item.get("duration")})
    if not videos:
        err = proc.stderr.strip()
        if any(h in err for h in BLOCK_HINTS):
            sys.exit("BLOCKED: this machine's network policy refused the connection to the site. "
                     "Allow its domains in the environment's Network access settings, or supply the "
                     "video files directly.\n" + err[-800:])
        sys.exit("No videos found.\n" + err[-800:])
    return videos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", help="Profile, channel or playlist URL")
    ap.add_argument("--question", default="Summarize this video: main points, what is shown, and any key claims.")
    ap.add_argument("--limit", type=int, default=20, help="Max videos to watch (default 20)")
    ap.add_argument("--engine", choices=["auto", "gemini", "local"], default=None)
    ap.add_argument("--detail", default=None, help="Passed to watch.py for the local engine")
    ap.add_argument("--out", default="profile-report.md", help="Combined report path")
    ap.add_argument("--list-only", action="store_true", help="Only list the videos")
    args = ap.parse_args()

    videos = list_videos(args.source, args.limit)
    print(f"[watch-profile] {len(videos)} video(s) found", file=sys.stderr)
    if args.list_only:
        for i, v in enumerate(videos, 1):
            print(f"{i}. {v['title']} ({v['duration']}s) {v['url']}")
        return 0

    out = Path(args.out)
    sections = [f"# Profile report: {args.source}\n\nQuestion: {args.question}\n"]
    failures = 0
    for i, v in enumerate(videos, 1):
        print(f"[watch-profile] {i}/{len(videos)} {v['url']}", file=sys.stderr)
        cmd = [sys.executable, str(WATCH_PY), v["url"], "--question", args.question]
        if args.engine:
            cmd += ["--engine", args.engine]
        if args.detail:
            cmd += ["--detail", args.detail]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        report = proc.stdout.strip() or proc.stderr.strip()
        if proc.returncode != 0 or "(failed)" in report:
            failures += 1
        sections.append(f"\n---\n\n## {i}. {v['title']}\n\n{v['url']}\n\n{report}\n")
        out.write_text("".join(sections))  # keep partial progress
    print(f"[watch-profile] wrote {out} ({len(videos) - failures} ok, {failures} failed)", file=sys.stderr)
    return 1 if failures == len(videos) else 0


if __name__ == "__main__":
    sys.exit(main())
