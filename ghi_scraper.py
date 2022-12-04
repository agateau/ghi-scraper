#!/usr/bin/env python3
"""
Scrap the issues of a GitHub project
"""
import argparse
import json
import logging
import os
import re
import sys

from itertools import count
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from typing import Any, Dict, Optional

import httpx

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

PAGE_SIZE = 100

logger = logging.getLogger()

LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s"


@dataclass
class ScrapInfo:
    project: str
    out_dir: Path
    since: Optional[datetime]


def is_pull_request(dct: Dict[str, Any]) -> bool:
    return "pull_request" in dct


def scrap_page(info: ScrapInfo, page: int) -> bool:
    logger.info("Scraping page %d", page)
    url = f"https://api.github.com/repos/{info.project}/issues"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
    }

    params = {
        "state": "all",
        "per_page": PAGE_SIZE,
        "page": page,
    }
    if info.since:
        params["since"] = info.since.isoformat()

    response = httpx.get(url, headers=headers, params=params)
    lst = response.json()
    assert isinstance(lst, list)
    if not lst:
        logger.info("Done")
        return False

    logger.info("Found %d item(s)", len(lst))
    for dct in lst:
        sub_dir = "pulls" if is_pull_request(dct) else "issues"
        item_dir = info.out_dir / sub_dir
        item_dir.mkdir(exist_ok=True)
        item_id = dct["number"]
        item_path = item_dir / f"{item_id}.json"

        text = json.dumps(dct, indent=2, sort_keys=True)
        logging.info("%s #%d: %s", sub_dir, item_id, dct["title"])
        item_path.write_text(text)

    return len(lst) == PAGE_SIZE


def scrap(info: ScrapInfo) -> None:
    if info.since:
        logger.info("Starting, scraping all issues for %s since %s", info.project, info.since)
    else:
        logger.info("Starting, scraping issues for %s", info.project)
    for page in count(1):
        if not scrap_page(info, page):
            return


def setup_logger():
    logging.basicConfig(level=logging.DEBUG,
                        format=LOG_FORMAT,
                        datefmt="%H:%M:%S")


def parse_since(since: str) -> datetime:
    try:
        return datetime.fromisoformat(since)
    except ValueError:
        pass
    match = re.fullmatch(r"(\d+)([wdHM])", since)
    if not match:
        sys.exit(f"'{since}' is not a valid date")

    value = int(match.group(1))
    unit = match.group(2)
    if unit == "w":
        delta = timedelta(weeks=value)
    elif unit == "d":
        delta = timedelta(days=value)
    elif unit == "H":
        delta = timedelta(hours=value)
    elif unit == "M":
        delta = timedelta(minutes=value)
    else:
        raise NotImplementedError

    return datetime.now() - delta


def main() -> int:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__)

    parser.add_argument("--since",
                        help="Import issues updated since DATE. Date can be either an ISO8601 date or a number followed by 'w', 'd', 'H', 'M' (weeks, days, hours, minutes)",
                        metavar="DATE")
    parser.add_argument("project", help="Project as a OWNER/REPO format")
    parser.add_argument("out_dir", help="Where to write the JSON files")

    args = parser.parse_args()

    if GITHUB_TOKEN == "":
        sys.exit("You must define the $GITHUB_TOKEN environment variable")

    out_dir = Path(args.out_dir)
    if not out_dir.is_dir():
        sys.exit(f"{out_dir} is not a directory")

    setup_logger()
    if args.since:
        since = parse_since(args.since)
    else:
        since = None
    scrap_info = ScrapInfo(args.project, out_dir, since)
    scrap(scrap_info)

    return 0


if __name__ == "__main__":
    sys.exit(main())
# vi: ts=4 sw=4 et
