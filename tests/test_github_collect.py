"""Tests for counting contributions from GitHub data (REQ-1.1, REQ-1.4, REQ-1.6)."""

from datetime import date

from contribution_tool.github import collect_github

START = date(2026, 9, 21)
END = date(2026, 10, 19)


def author(login):
    return {"login": login} if login else None


def review(login, submitted="2026-10-02T10:00:00Z", comments=0):
    return {"author": author(login), "submittedAt": submitted, "comments": {"totalCount": comments}}


def pr(login="ogrencibir", created="2026-10-01T10:00:00Z", merged=None, reviews=(), commits=()):
    return {
        "number": 1,
        "title": "Test PR",
        "url": "https://example.org/pull/1",
        "author": author(login),
        "createdAt": created,
        "mergedAt": merged,
        "reviews": {"nodes": list(reviews)},
        "commits": {"nodes": list(commits)},
    }


def commit(email, login):
    return {"commit": {"author": {"email": email, "user": author(login)}}}


def post(login, created="2026-10-03T10:00:00Z", replies=()):
    return {"author": author(login), "createdAt": created, "replies": {"nodes": list(replies)}}


def discussion(login, comments=(), created="2026-10-03T10:00:00Z"):
    return {"author": author(login), "createdAt": created, "comments": {"nodes": list(comments)}}


# REQ-1.1 — Pull requests, reviews and discussions are counted


def test_opened_pull_request_is_counted():
    data = collect_github([pr()])
    assert data.counts["ogrencibir"]["pr_opened"] == 1
    assert data.counts["ogrencibir"]["pr_merged"] == 0


def test_merged_pull_request_is_counted():
    data = collect_github([pr(merged="2026-10-04T10:00:00Z")])
    assert data.counts["ogrencibir"]["pr_merged"] == 1


def test_review_and_review_comments_are_counted_for_reviewer():
    data = collect_github([pr(reviews=[review("ogrenciiki", comments=3)])])
    assert data.counts["ogrenciiki"]["reviews"] == 1
    assert data.counts["ogrenciiki"]["review_comments"] == 3


def test_several_reviews_on_one_pull_request_count_once():
    reviews = [review("ogrenciiki", comments=2), review("ogrenciiki", comments=1)]
    data = collect_github([pr(reviews=reviews)])
    assert data.counts["ogrenciiki"]["reviews"] == 1
    assert data.counts["ogrenciiki"]["review_comments"] == 3


def test_discussion_post_comment_and_reply_are_counted():
    thread = discussion("ogrencibir", comments=[post("ogrenciiki", replies=[post("ogrencibir")])])
    data = collect_github([], [thread])
    assert data.counts["ogrencibir"]["discussion_posts"] == 2
    assert data.counts["ogrenciiki"]["discussion_posts"] == 1


def test_logins_are_lowercased():
    assert collect_github([pr(login="OgrenciBir")]).counts["ogrencibir"]["pr_opened"] == 1


def test_users_with_contributions_are_listed():
    data = collect_github([pr(reviews=[review("ogrenciiki")])])
    assert data.users == {"ogrencibir", "ogrenciiki"}


def test_commit_emails_are_mapped_to_logins():
    data = collect_github([pr(commits=[commit("Bir@Example.ORG", "OgrenciBir")])])
    assert data.emails == {"bir@example.org": {"ogrencibir"}}


# REQ-1.3 — Date range is applied to each kind of contribution


def test_pull_request_opened_before_range_but_merged_inside_counts_only_as_merged():
    old_pr = pr(created="2026-09-15T10:00:00Z", merged="2026-09-22T10:00:00Z")
    data = collect_github([old_pr], start=START, end=END)
    assert data.counts["ogrencibir"]["pr_opened"] == 0
    assert data.counts["ogrencibir"]["pr_merged"] == 1


def test_review_after_range_is_not_counted():
    late = review("ogrenciiki", submitted="2026-10-20T10:00:00Z", comments=2)
    data = collect_github([pr(reviews=[late])], start=START, end=END)
    assert data.counts["ogrenciiki"]["reviews"] == 0
    assert data.counts["ogrenciiki"]["review_comments"] == 0


def test_discussion_comment_before_range_is_not_counted():
    thread = discussion("ogrencibir", comments=[post("ogrenciiki", created="2026-09-01T10:00:00Z")])
    data = collect_github([], [thread], start=START, end=END)
    assert data.counts["ogrenciiki"]["discussion_posts"] == 0


# REQ-1.4 — Bots and deleted accounts are not counted


def test_pull_request_by_bot_is_not_counted():
    data = collect_github([pr(login="dependabot[bot]")])
    assert data.users == set()


def test_review_by_bot_is_not_counted():
    data = collect_github([pr(reviews=[review("github-actions[bot]")])])
    assert "github-actions[bot]" not in data.users


def test_deleted_account_is_skipped():
    data = collect_github([pr(login=None, reviews=[review(None)])])
    assert data.users == set()


def test_bot_commit_email_is_not_mapped():
    data = collect_github([pr(commits=[commit("bot@example.org", "renovate[bot]")])])
    assert data.emails == {}


# REQ-1.6 — Reviewing your own pull request is not a review


def test_review_on_own_pull_request_is_not_counted():
    data = collect_github([pr(reviews=[review("ogrencibir", comments=4)])])
    assert data.counts["ogrencibir"]["reviews"] == 0
    assert data.counts["ogrencibir"]["review_comments"] == 0
