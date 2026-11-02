"""Downloading pull requests and discussions from the GitHub GraphQL API (REQ-1.1, REQ-6.2)."""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

API_URL = "https://api.github.com/graphql"
TOKEN_VARIABLE = "GITHUB_TOKEN"

Request = Callable[[str, dict[str, Any]], dict[str, Any]]

PULL_REQUESTS_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: 50, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title url createdAt mergedAt author { login }
        reviews(first: 100) {
          nodes { author { login } submittedAt comments { totalCount } }
        }
        commits(first: 100) {
          nodes { commit { author { email user { login } } } }
        }
      }
    }
  }
}
"""

DISCUSSIONS_QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    discussions(first: 25, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        id title url createdAt author { login }
        comments(first: 100) {
          pageInfo { hasNextPage endCursor }
          nodes {
            createdAt author { login }
            replies(first: 100) { nodes { createdAt author { login } } }
          }
        }
      }
    }
  }
}
"""

MORE_COMMENTS_QUERY = """
query($id: ID!, $cursor: String) {
  node(id: $id) {
    ... on Discussion {
      comments(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          createdAt author { login }
          replies(first: 100) { nodes { createdAt author { login } } }
        }
      }
    }
  }
}
"""


def get_token(environ: Mapping[str, str] = os.environ) -> str:
    """Read the GitHub token from the environment, never from code (REQ-6.2)."""
    token = environ.get(TOKEN_VARIABLE, "").strip()
    if not token:
        raise RuntimeError(
            f"{TOKEN_VARIABLE} is not set. Create a read-only token on GitHub and run:\n"
            f'  export {TOKEN_VARIABLE}="..."'
        )
    return token


def graphql_request(token: str) -> Request:
    """Return a function that sends one GraphQL query with the given token."""

    def send(query: str, variables: dict[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            API_URL,
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read())
        if body.get("errors"):
            raise RuntimeError(f"GitHub API error: {body['errors'][0].get('message')}")
        return body["data"]

    return send


def split_repo(repo: str) -> tuple[str, str]:
    """Split 'owner/name' into its two parts."""
    parts = repo.split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"Repository must be written as 'owner/name', got '{repo}'")
    return parts[0], parts[1]


def fetch_pull_requests(repo: str, request: Request) -> list[dict[str, Any]]:
    """Download all pull requests of a repository, page by page."""
    owner, name = split_repo(repo)
    return _all_pages(request, PULL_REQUESTS_QUERY, {"owner": owner, "name": name}, "pullRequests")


def fetch_discussions(repo: str, request: Request) -> list[dict[str, Any]]:
    """Download all discussions with all their comments, page by page."""
    owner, name = split_repo(repo)
    discussions = _all_pages(
        request, DISCUSSIONS_QUERY, {"owner": owner, "name": name}, "discussions"
    )
    for discussion in discussions:
        comments = discussion["comments"]
        while comments["pageInfo"]["hasNextPage"]:
            variables = {"id": discussion["id"], "cursor": comments["pageInfo"]["endCursor"]}
            more = request(MORE_COMMENTS_QUERY, variables)["node"]["comments"]
            comments["nodes"].extend(more["nodes"])
            comments["pageInfo"] = more["pageInfo"]
    return discussions


def _all_pages(
    request: Request, query: str, variables: dict[str, Any], connection: str
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    cursor = None
    while True:
        page = request(query, {**variables, "cursor": cursor})["repository"][connection]
        nodes.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return nodes
        cursor = page["pageInfo"]["endCursor"]
