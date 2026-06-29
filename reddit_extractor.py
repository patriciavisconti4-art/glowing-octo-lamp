"""
Reddit Data Extractor

Extracts posts and comments from Reddit subreddits using the PRAW library
and saves the data to CSV or JSON for analysis.

Usage:
    python reddit_extractor.py --subreddit python --limit 100 --output posts.csv
    python reddit_extractor.py --subreddit python --mode comments --limit 50 --output comments.json --format json

Environment variables (or pass directly):
    REDDIT_CLIENT_ID      - Your Reddit app client ID
    REDDIT_CLIENT_SECRET  - Your Reddit app client secret
    REDDIT_USER_AGENT     - A descriptive user agent string
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from typing import Iterator

import praw
from praw.models import Comment, Submission


def create_reddit_client(
    client_id: str | None = None,
    client_secret: str | None = None,
    user_agent: str | None = None,
) -> praw.Reddit:
    """Create and return an authenticated Reddit client.

    Credentials are read from arguments first, then environment variables.

    Args:
        client_id: Reddit app client ID.
        client_secret: Reddit app client secret.
        user_agent: Descriptive user agent string.

    Returns:
        An authenticated praw.Reddit instance (read-only).

    Raises:
        ValueError: If any required credential is missing.
    """
    client_id = client_id or os.environ.get("REDDIT_CLIENT_ID")
    client_secret = client_secret or os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = user_agent or os.environ.get(
        "REDDIT_USER_AGENT", "reddit-data-extractor/1.0"
    )

    if not client_id:
        raise ValueError(
            "Reddit client ID is required. Set REDDIT_CLIENT_ID environment variable "
            "or pass --client-id."
        )
    if not client_secret:
        raise ValueError(
            "Reddit client secret is required. Set REDDIT_CLIENT_SECRET environment "
            "variable or pass --client-secret."
        )

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        read_only=True,
    )


def _utc_timestamp(epoch: float) -> str:
    """Convert a UTC epoch timestamp to an ISO-8601 string."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def extract_posts(
    reddit: praw.Reddit,
    subreddit_name: str,
    sort: str = "hot",
    limit: int = 100,
) -> Iterator[dict]:
    """Yield post data dicts from a subreddit.

    Args:
        reddit: Authenticated Reddit client.
        subreddit_name: Name of the subreddit (without 'r/').
        sort: Feed to pull from: 'hot', 'new', 'top', or 'rising'.
        limit: Maximum number of posts to retrieve (1-1000).

    Yields:
        Dicts with post metadata and text fields.
    """
    subreddit = reddit.subreddit(subreddit_name)
    feed = {
        "hot": subreddit.hot,
        "new": subreddit.new,
        "top": subreddit.top,
        "rising": subreddit.rising,
    }.get(sort, subreddit.hot)

    for post in feed(limit=limit):
        yield {
            "id": post.id,
            "title": post.title,
            "author": str(post.author) if post.author else "[deleted]",
            "subreddit": post.subreddit.display_name,
            "score": post.score,
            "upvote_ratio": post.upvote_ratio,
            "num_comments": post.num_comments,
            "url": post.url,
            "permalink": f"https://www.reddit.com{post.permalink}",
            "selftext": post.selftext,
            "is_self": post.is_self,
            "created_utc": _utc_timestamp(post.created_utc),
            "flair": post.link_flair_text,
        }


def extract_comments(
    reddit: praw.Reddit,
    subreddit_name: str,
    sort: str = "hot",
    post_limit: int = 10,
    comment_limit: int | None = None,
) -> Iterator[dict]:
    """Yield comment data dicts from posts in a subreddit.

    Args:
        reddit: Authenticated Reddit client.
        subreddit_name: Name of the subreddit (without 'r/').
        sort: Feed sort for selecting posts: 'hot', 'new', 'top', or 'rising'.
        post_limit: Number of posts to pull comments from.
        comment_limit: Max comments per post (None = all top-level comments).

    Yields:
        Dicts with comment metadata and body text.
    """
    subreddit = reddit.subreddit(subreddit_name)
    feed = {
        "hot": subreddit.hot,
        "new": subreddit.new,
        "top": subreddit.top,
        "rising": subreddit.rising,
    }.get(sort, subreddit.hot)

    for post in feed(limit=post_limit):
        post.comments.replace_more(limit=0)
        comments = post.comments.list()
        if comment_limit is not None:
            comments = comments[:comment_limit]

        for comment in comments:
            if not isinstance(comment, Comment):
                continue
            yield {
                "comment_id": comment.id,
                "post_id": post.id,
                "post_title": post.title,
                "subreddit": post.subreddit.display_name,
                "author": str(comment.author) if comment.author else "[deleted]",
                "body": comment.body,
                "score": comment.score,
                "depth": comment.depth,
                "is_submitter": comment.is_submitter,
                "created_utc": _utc_timestamp(comment.created_utc),
                "permalink": f"https://www.reddit.com{comment.permalink}",
            }


def save_to_csv(records: list[dict], output_path: str) -> None:
    """Write a list of dicts to a CSV file.

    Args:
        records: List of record dicts (all with the same keys).
        output_path: Destination file path.
    """
    if not records:
        print("No records to save.", file=sys.stderr)
        return

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    print(f"Saved {len(records)} records to {output_path}")


def save_to_json(records: list[dict], output_path: str) -> None:
    """Write a list of dicts to a JSON file.

    Args:
        records: List of record dicts.
        output_path: Destination file path.
    """
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, ensure_ascii=False, indent=2)

    print(f"Saved {len(records)} records to {output_path}")


def build_argument_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Extract posts or comments from a Reddit subreddit."
    )
    parser.add_argument(
        "--subreddit",
        required=True,
        help="Subreddit name (without 'r/')",
    )
    parser.add_argument(
        "--mode",
        choices=["posts", "comments"],
        default="posts",
        help="Data type to extract (default: posts)",
    )
    parser.add_argument(
        "--sort",
        choices=["hot", "new", "top", "rising"],
        default="hot",
        help="Feed sort order (default: hot)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of posts to retrieve (default: 100)",
    )
    parser.add_argument(
        "--comment-limit",
        type=int,
        default=None,
        help="Max comments per post when mode=comments (default: all)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output file path (default: <subreddit>_<mode>_<timestamp>.csv)",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Output format (default: csv)",
    )
    parser.add_argument("--client-id", default=None, help="Reddit app client ID")
    parser.add_argument(
        "--client-secret", default=None, help="Reddit app client secret"
    )
    parser.add_argument("--user-agent", default=None, help="Reddit user agent string")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Entry point for the CLI."""
    parser = build_argument_parser()
    args = parser.parse_args(argv)

    reddit = create_reddit_client(
        client_id=args.client_id,
        client_secret=args.client_secret,
        user_agent=args.user_agent,
    )

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
    output_path = args.output or (
        f"{args.subreddit}_{args.mode}_{timestamp}.{args.format}"
    )

    if args.mode == "posts":
        records = list(
            extract_posts(
                reddit,
                subreddit_name=args.subreddit,
                sort=args.sort,
                limit=args.limit,
            )
        )
    else:
        records = list(
            extract_comments(
                reddit,
                subreddit_name=args.subreddit,
                sort=args.sort,
                post_limit=args.limit,
                comment_limit=args.comment_limit,
            )
        )

    if args.format == "json":
        save_to_json(records, output_path)
    else:
        save_to_csv(records, output_path)


if __name__ == "__main__":
    main()
