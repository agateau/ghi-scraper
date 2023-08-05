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
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.aiohttp import log as gql_transport_logger

logger = logging.getLogger()

LOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s"

SCHEMA_PATH = Path(__file__).parent / "github-schema.graphql"

FORMAT_KEY = "_format"
FORMAT = 2


@dataclass
class ScrapInfo:
    project: str
    out_dir: Path
    since: Optional[datetime]


def is_pull_request(dct: Dict[str, Any]) -> bool:
    return "pull_request" in dct


def scrap_page(client: Client, info: ScrapInfo, cursor: str | None) -> str | None:
    logger.info("Scraping page %s", cursor)
    query = gql(
        """
        query($owner: String!, $name: String!, $since: DateTime, $issues_after: String) {
            repository(owner: $owner, name: $name) {
            issues(after: $issues_after, filterBy: { since: $since }, first: 20) {
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                    edges {
                        node {
                            number
                            title
                            url
                            body
                            state
                            createdAt
                            updatedAt
                            author {
                                login
                                url
                            }
                            labels(first: 20) {
                                edges {
                                    node {
                                        name
                                    }
                                }
                            }
                            comments(first: 100) {
                                edges {
                                    node {
                                        author {
                                            login
                                            url
                                        }
                                        createdAt
                                        lastEditedAt
                                        body
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """
    )

    owner, name = info.project.split("/")

    params = {
        "owner": owner,
        "name": name,
        "since": info.since.isoformat() if info.since else None,
        "issues_after": cursor,
    }

    result = client.execute(query, variable_values=params)

    edges = result["repository"]["issues"]["edges"]
    page_info = result["repository"]["issues"]["pageInfo"]
    for edge in edges:
        dct = edge["node"]
        dct[FORMAT_KEY] = FORMAT
        sub_dir = "issues"
        item_dir = info.out_dir / sub_dir
        item_dir.mkdir(exist_ok=True)
        item_id = dct["number"]
        item_path = item_dir / f"{item_id}.json"

        text = json.dumps(dct, indent=2, sort_keys=True)
        logging.info("%s #%d: %s", sub_dir, item_id, dct["title"])
        item_path.write_text(text)

    if page_info["hasNextPage"]:
        return page_info["endCursor"]
    return None


def scrap(client: Client, info: ScrapInfo) -> None:
    if info.since:
        logger.info(
            "Starting, scraping all issues for %s since %s", info.project, info.since
        )
    else:
        logger.info("Starting, scraping issues for %s", info.project)
    cursor = None
    while True:
        cursor = scrap_page(client, info, cursor)
        if cursor is None:
            return


def setup_logger():
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt="%H:%M:%S")
    # Mute GQL transport a bit: it logs all responses at INFO level
    gql_transport_logger.setLevel(logging.WARNING)


def parse_since(since: str) -> datetime:
    try:
        return datetime.fromisoformat(since)
    except ValueError:
        pass
    match = re.fullmatch(r"(\d+)([wdh])", since)
    if not match:
        sys.exit(f"'{since}' is not a valid date")

    value = int(match.group(1))
    unit = match.group(2)
    if unit == "w":
        delta = timedelta(weeks=value)
    elif unit == "d":
        delta = timedelta(days=value)
    elif unit == "h":
        delta = timedelta(hours=value)
    else:
        raise NotImplementedError

    return datetime.now() - delta


def create_client(github_token: str) -> Client:
    schema = SCHEMA_PATH.read_text()

    transport = AIOHTTPTransport(
        url="https://api.github.com/graphql",
        headers={"Authorization": f"Bearer {github_token}"},
    )
    return Client(transport=transport, schema=schema)


def main() -> int:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__
    )

    parser.add_argument(
        "--since",
        help="Import issues updated since DATE. Date can be either an ISO8601 date or a number followed by 'w', 'd', 'h' (weeks, days, hours)",
        metavar="DATE",
    )
    parser.add_argument("project", help="Project as a OWNER/REPO format")
    parser.add_argument("out_dir", help="Where to write the JSON files")

    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_dir():
        sys.exit(f"{out_dir} is not a directory")

    setup_logger()

    github_token = os.getenv("GITHUB_TOKEN", "")
    if github_token == "":
        logger.error("$GITHUB_TOKEN environment variable not set")
        return 1

    client = create_client(github_token)

    if args.since:
        since = parse_since(args.since)
    else:
        since = None
    scrap_info = ScrapInfo(args.project, out_dir, since)
    scrap(client, scrap_info)

    return 0


if __name__ == "__main__":
    sys.exit(main())
# vi: ts=4 sw=4 et
