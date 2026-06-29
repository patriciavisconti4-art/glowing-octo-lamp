"""
Unit tests for reddit_extractor.py.

All Reddit API calls are mocked so no real credentials are required.
"""

import csv
import json
import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import reddit_extractor as re_mod


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_submission(
    id="abc123",
    title="Test Post",
    author="user1",
    subreddit="python",
    score=42,
    upvote_ratio=0.95,
    num_comments=5,
    url="https://example.com",
    permalink="/r/python/comments/abc123/test/",
    selftext="Hello world",
    is_self=True,
    created_utc=1_700_000_000.0,
    flair=None,
):
    sub = MagicMock()
    sub.id = id
    sub.title = title
    sub.author = SimpleNamespace(__str__=lambda s: author)
    sub.subreddit = SimpleNamespace(display_name=subreddit)
    sub.score = score
    sub.upvote_ratio = upvote_ratio
    sub.num_comments = num_comments
    sub.url = url
    sub.permalink = permalink
    sub.selftext = selftext
    sub.is_self = is_self
    sub.created_utc = created_utc
    sub.link_flair_text = flair
    return sub


def _make_comment(
    id="cmt1",
    post_id="abc123",
    post_title="Test Post",
    subreddit="python",
    author="commenter",
    body="Great post!",
    score=10,
    depth=0,
    is_submitter=False,
    created_utc=1_700_001_000.0,
    permalink="/r/python/comments/abc123/test/cmt1/",
):
    from praw.models import Comment

    cmt = MagicMock(spec=Comment)
    cmt.id = id
    cmt.author = SimpleNamespace(__str__=lambda s: author)
    cmt.body = body
    cmt.score = score
    cmt.depth = depth
    cmt.is_submitter = is_submitter
    cmt.created_utc = created_utc
    cmt.permalink = permalink
    return cmt


# ---------------------------------------------------------------------------
# create_reddit_client
# ---------------------------------------------------------------------------


class TestCreateRedditClient:
    def test_raises_without_client_id(self):
        with pytest.raises(ValueError, match="client ID"):
            re_mod.create_reddit_client(
                client_id=None, client_secret="secret", user_agent="agent"
            )

    def test_raises_without_client_secret(self):
        with pytest.raises(ValueError, match="client secret"):
            re_mod.create_reddit_client(
                client_id="id", client_secret=None, user_agent="agent"
            )

    def test_reads_credentials_from_env(self):
        env = {
            "REDDIT_CLIENT_ID": "env_id",
            "REDDIT_CLIENT_SECRET": "env_secret",
            "REDDIT_USER_AGENT": "env_agent",
        }
        with patch.dict(os.environ, env):
            with patch("praw.Reddit") as mock_reddit:
                re_mod.create_reddit_client()
                mock_reddit.assert_called_once_with(
                    client_id="env_id",
                    client_secret="env_secret",
                    user_agent="env_agent",
                    read_only=True,
                )

    def test_explicit_args_take_precedence_over_env(self):
        env = {
            "REDDIT_CLIENT_ID": "env_id",
            "REDDIT_CLIENT_SECRET": "env_secret",
        }
        with patch.dict(os.environ, env):
            with patch("praw.Reddit") as mock_reddit:
                re_mod.create_reddit_client(
                    client_id="arg_id",
                    client_secret="arg_secret",
                    user_agent="arg_agent",
                )
                mock_reddit.assert_called_once_with(
                    client_id="arg_id",
                    client_secret="arg_secret",
                    user_agent="arg_agent",
                    read_only=True,
                )

    def test_client_is_read_only(self):
        with patch("praw.Reddit") as mock_reddit:
            re_mod.create_reddit_client(
                client_id="id", client_secret="secret", user_agent="agent"
            )
            _, kwargs = mock_reddit.call_args
            assert kwargs["read_only"] is True


# ---------------------------------------------------------------------------
# extract_posts
# ---------------------------------------------------------------------------


class TestExtractPosts:
    def _reddit_with_posts(self, posts, sort="hot"):
        reddit = MagicMock()
        subreddit = MagicMock()
        getattr(subreddit, sort).return_value = iter(posts)
        reddit.subreddit.return_value = subreddit
        return reddit

    def test_yields_correct_fields(self):
        post = _make_submission()
        reddit = self._reddit_with_posts([post])
        results = list(re_mod.extract_posts(reddit, "python", sort="hot", limit=1))
        assert len(results) == 1
        r = results[0]
        assert r["id"] == "abc123"
        assert r["title"] == "Test Post"
        assert r["subreddit"] == "python"
        assert r["score"] == 42
        assert r["is_self"] is True
        assert r["permalink"] == "https://www.reddit.com/r/python/comments/abc123/test/"

    def test_deleted_author_shown_as_deleted(self):
        post = _make_submission()
        post.author = None
        reddit = self._reddit_with_posts([post])
        results = list(re_mod.extract_posts(reddit, "python", sort="hot", limit=1))
        assert results[0]["author"] == "[deleted]"

    def test_uses_correct_sort_feed(self):
        reddit = MagicMock()
        subreddit = MagicMock()
        subreddit.new.return_value = iter([])
        reddit.subreddit.return_value = subreddit

        list(re_mod.extract_posts(reddit, "python", sort="new", limit=5))
        subreddit.new.assert_called_once_with(limit=5)

    def test_unknown_sort_falls_back_to_hot(self):
        reddit = MagicMock()
        subreddit = MagicMock()
        subreddit.hot.return_value = iter([])
        reddit.subreddit.return_value = subreddit

        list(re_mod.extract_posts(reddit, "python", sort="bogus", limit=5))
        subreddit.hot.assert_called_once_with(limit=5)

    def test_created_utc_is_iso_string(self):
        post = _make_submission(created_utc=0.0)
        reddit = self._reddit_with_posts([post])
        results = list(re_mod.extract_posts(reddit, "python"))
        assert results[0]["created_utc"].startswith("1970-01-01")


# ---------------------------------------------------------------------------
# extract_comments
# ---------------------------------------------------------------------------


class TestExtractComments:
    def _reddit_with_comments(self, posts_and_comments):
        reddit = MagicMock()
        subreddit = MagicMock()

        mock_posts = []
        for post_mock, comments in posts_and_comments:
            post_mock.comments = MagicMock()
            post_mock.comments.replace_more.return_value = None
            post_mock.comments.list.return_value = comments
            mock_posts.append(post_mock)

        subreddit.hot.return_value = iter(mock_posts)
        reddit.subreddit.return_value = subreddit
        return reddit

    def test_yields_correct_fields(self):
        post = _make_submission()
        comment = _make_comment()
        reddit = self._reddit_with_comments([(post, [comment])])

        results = list(re_mod.extract_comments(reddit, "python", post_limit=1))
        assert len(results) == 1
        r = results[0]
        assert r["comment_id"] == "cmt1"
        assert r["post_id"] == "abc123"
        assert r["body"] == "Great post!"
        assert r["score"] == 10
        assert r["depth"] == 0

    def test_comment_limit_respected(self):
        from praw.models import Comment

        post = _make_submission()
        comments = [_make_comment(id=f"c{i}") for i in range(10)]
        reddit = self._reddit_with_comments([(post, comments)])

        results = list(
            re_mod.extract_comments(reddit, "python", post_limit=1, comment_limit=3)
        )
        assert len(results) == 3

    def test_deleted_author_shown_as_deleted(self):
        post = _make_submission()
        comment = _make_comment()
        comment.author = None
        reddit = self._reddit_with_comments([(post, [comment])])

        results = list(re_mod.extract_comments(reddit, "python", post_limit=1))
        assert results[0]["author"] == "[deleted]"

    def test_non_comment_objects_skipped(self):
        post = _make_submission()
        # A MoreComments object (not a Comment instance) should be skipped
        more = MagicMock()  # not spec'd as Comment
        from praw.models import Comment

        comment = _make_comment()
        reddit = self._reddit_with_comments([(post, [more, comment])])

        results = list(re_mod.extract_comments(reddit, "python", post_limit=1))
        assert len(results) == 1


# ---------------------------------------------------------------------------
# save_to_csv / save_to_json
# ---------------------------------------------------------------------------


class TestSaveToCSV:
    def test_writes_header_and_rows(self):
        records = [{"a": 1, "b": 2}, {"a": 3, "b": 4}]
        with tempfile.NamedTemporaryFile(
            mode="r", suffix=".csv", delete=False
        ) as tmp:
            path = tmp.name

        re_mod.save_to_csv(records, path)
        with open(path, encoding="utf-8") as fh:
            reader = list(csv.DictReader(fh))
        assert reader[0]["a"] == "1"
        assert reader[1]["b"] == "4"
        os.unlink(path)

    def test_empty_records_does_not_write(self, capsys):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = tmp.name

        re_mod.save_to_csv([], path)
        captured = capsys.readouterr()
        assert "No records" in captured.err
        os.unlink(path)


class TestSaveToJSON:
    def test_writes_valid_json(self):
        records = [{"x": "hello"}, {"x": "world"}]
        with tempfile.NamedTemporaryFile(
            mode="r", suffix=".json", delete=False
        ) as tmp:
            path = tmp.name

        re_mod.save_to_json(records, path)
        with open(path, encoding="utf-8") as fh:
            loaded = json.load(fh)
        assert loaded == records
        os.unlink(path)


# ---------------------------------------------------------------------------
# CLI (main)
# ---------------------------------------------------------------------------


class TestCLI:
    def _mock_reddit(self, records):
        reddit = MagicMock()
        return reddit

    def test_main_posts_csv(self, tmp_path):
        out = str(tmp_path / "out.csv")
        post = _make_submission()
        reddit_mock = MagicMock()
        subreddit_mock = MagicMock()
        subreddit_mock.hot.return_value = iter([post])
        reddit_mock.subreddit.return_value = subreddit_mock

        with patch("reddit_extractor.create_reddit_client", return_value=reddit_mock):
            re_mod.main(
                [
                    "--subreddit", "python",
                    "--mode", "posts",
                    "--limit", "1",
                    "--output", out,
                    "--client-id", "id",
                    "--client-secret", "secret",
                ]
            )

        assert os.path.exists(out)
        with open(out, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == 1
        assert rows[0]["id"] == "abc123"

    def test_main_posts_json(self, tmp_path):
        out = str(tmp_path / "out.json")
        post = _make_submission()
        reddit_mock = MagicMock()
        subreddit_mock = MagicMock()
        subreddit_mock.hot.return_value = iter([post])
        reddit_mock.subreddit.return_value = subreddit_mock

        with patch("reddit_extractor.create_reddit_client", return_value=reddit_mock):
            re_mod.main(
                [
                    "--subreddit", "python",
                    "--mode", "posts",
                    "--limit", "1",
                    "--output", out,
                    "--format", "json",
                    "--client-id", "id",
                    "--client-secret", "secret",
                ]
            )

        with open(out, encoding="utf-8") as fh:
            data = json.load(fh)
        assert len(data) == 1

    def test_main_comments_mode(self, tmp_path):
        from praw.models import Comment

        out = str(tmp_path / "comments.csv")
        post = _make_submission()
        comment = _make_comment()
        post.comments = MagicMock()
        post.comments.replace_more.return_value = None
        post.comments.list.return_value = [comment]

        reddit_mock = MagicMock()
        subreddit_mock = MagicMock()
        subreddit_mock.hot.return_value = iter([post])
        reddit_mock.subreddit.return_value = subreddit_mock

        with patch("reddit_extractor.create_reddit_client", return_value=reddit_mock):
            re_mod.main(
                [
                    "--subreddit", "python",
                    "--mode", "comments",
                    "--limit", "1",
                    "--output", out,
                    "--client-id", "id",
                    "--client-secret", "secret",
                ]
            )

        assert os.path.exists(out)
