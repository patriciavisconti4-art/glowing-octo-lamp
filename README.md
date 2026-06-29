# Reddit Data Extractor

A Python tool for extracting posts and comments from Reddit subreddits using the [PRAW](https://praw.readthedocs.io/) library and saving the results to CSV or JSON for analysis.

## Requirements

- Python 3.10+
- A Reddit app (free) for API credentials — [create one here](https://www.reddit.com/prefs/apps)

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set your Reddit API credentials as environment variables:

```bash
export REDDIT_CLIENT_ID="your_client_id"
export REDDIT_CLIENT_SECRET="your_client_secret"
export REDDIT_USER_AGENT="my-data-extractor/1.0"   # optional
```

Alternatively, pass them as CLI flags (`--client-id`, `--client-secret`, `--user-agent`).

## Usage

### Extract posts

```bash
# Top 100 hot posts from r/python → python_posts_<timestamp>.csv
python reddit_extractor.py --subreddit python

# 200 newest posts → output.json
python reddit_extractor.py --subreddit MachineLearning --sort new --limit 200 \
    --output ml_posts.json --format json
```

### Extract comments

```bash
# Comments from the top 10 hot posts in r/datascience
python reddit_extractor.py --subreddit datascience --mode comments --limit 10

# Limit to 50 comments per post
python reddit_extractor.py --subreddit datascience --mode comments \
    --limit 10 --comment-limit 50 --output comments.csv
```

### All options

```
usage: reddit_extractor.py [-h] --subreddit SUBREDDIT [--mode {posts,comments}]
                           [--sort {hot,new,top,rising}] [--limit LIMIT]
                           [--comment-limit COMMENT_LIMIT] [--output OUTPUT]
                           [--format {csv,json}] [--client-id CLIENT_ID]
                           [--client-secret CLIENT_SECRET] [--user-agent USER_AGENT]
```

| Flag | Default | Description |
|---|---|---|
| `--subreddit` | *(required)* | Subreddit name (without `r/`) |
| `--mode` | `posts` | `posts` or `comments` |
| `--sort` | `hot` | `hot`, `new`, `top`, or `rising` |
| `--limit` | `100` | Posts to retrieve (1–1000) |
| `--comment-limit` | all | Max comments per post (comments mode only) |
| `--output` | auto | Output file path |
| `--format` | `csv` | `csv` or `json` |

## Output fields

**Posts** (`--mode posts`)

| Field | Description |
|---|---|
| `id` | Reddit post ID |
| `title` | Post title |
| `author` | Username (or `[deleted]`) |
| `subreddit` | Subreddit name |
| `score` | Upvote score |
| `upvote_ratio` | Ratio of upvotes to total votes |
| `num_comments` | Comment count |
| `url` | Link URL |
| `permalink` | Full Reddit permalink |
| `selftext` | Body text for text posts |
| `is_self` | `True` if text post, `False` if link post |
| `created_utc` | Post creation time (ISO-8601 UTC) |
| `flair` | Post flair text |

**Comments** (`--mode comments`)

| Field | Description |
|---|---|
| `comment_id` | Reddit comment ID |
| `post_id` | Parent post ID |
| `post_title` | Parent post title |
| `subreddit` | Subreddit name |
| `author` | Username (or `[deleted]`) |
| `body` | Comment text |
| `score` | Upvote score |
| `depth` | Nesting depth (0 = top-level) |
| `is_submitter` | `True` if the commenter is the post author |
| `created_utc` | Comment creation time (ISO-8601 UTC) |
| `permalink` | Full Reddit permalink |

## Running tests

```bash
pip install pytest
python -m pytest tests/ -v
```
