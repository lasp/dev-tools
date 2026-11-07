#!/usr/bin/env python3
"""A read-only stand-in for github-mcp-server, serving the fixed issues and pull requests in
`github.json` beside it over stdio, so a scenario reads a GitHub issue tracker with no GitHub. Its
name holds `github-mcp-server`, so `run.py` gives it the GitHub rules: the read tools allowed and
every write denied, which it has none of.

    {"command": "python3", "args": ["-I", "<this file>"]}

Its tools are github-mcp-server's by name, arguments and output shape, as read from the real
server: `get_me`; `issue_read` with the methods `get`, `get_comments`, `get_labels` and
`get_parent`, where `get` gives labels by name and `get_labels` as objects, `get_parent` gives a
null parent, since no fixture issue has one, and `get` on a pull request's number returns it as
an issue whose `html_url` holds `/pull/`, as GitHub's issue API does; `list_issues`, whose states
are upper-case, as the server's GraphQL gives them; `search_issues`, which returns the issues
sharing a word of three letters or more with the query; and `search_pull_requests`, which returns
the pull requests whose title or body holds every quoted phrase of the query and every bare word
that is not a qualifier such as `repo:`, `is:`, `in:` or `state:`, matched by whole words and
numbers, punctuation dropped, as GitHub's search does, its links naming the repository the query's
`repo:` gives when the call names none. Every
repository is served the same fixture, whatever the owner. A number the fixture
does not hold is an error result. Stdlib only.
"""

import json
import re
import sys
from pathlib import Path

DATA = json.loads((Path(__file__).with_name("github.json")).read_text())
ISSUES = {i["number"]: i for i in DATA["issues"]}
PULLS = {p["number"]: p for p in DATA["pulls"]}
LABELS = {label["name"]: label for label in DATA["labels"]}
NUMBER = {"type": "number"}
TEXT = {"type": "string"}
REPO = {"owner": TEXT, "repo": TEXT}
FIELDS = {"type": "array", "items": {"type": "string"}}
SEARCH = {"query": TEXT, "owner": TEXT, "repo": TEXT, "sort": TEXT, "order": TEXT, "page": NUMBER, "perPage": NUMBER, "fields": FIELDS}

TOOLS = {
    "get_me": ("Get details of the authenticated GitHub user.", {}, []),
    "issue_read": ("Get information about a specific issue in a GitHub repository.",
                   {"method": {"type": "string", "enum": ["get", "get_comments", "get_sub_issues", "get_parent", "get_labels"]},
                    **REPO, "issue_number": NUMBER, "page": NUMBER, "perPage": NUMBER},
                   ["method", "owner", "repo", "issue_number"]),
    "list_issues": ("List issues in a GitHub repository.",
                    {**REPO, "state": {"type": "string", "enum": ["OPEN", "CLOSED"]}, "labels": FIELDS, "perPage": NUMBER,
                     "after": TEXT, "since": TEXT, "orderBy": TEXT, "direction": TEXT, "fields": FIELDS},
                    ["owner", "repo"]),
    "search_issues": ("Search issues using natural-language semantic matching. Already scoped to is:issue.", SEARCH, ["query"]),
    "search_pull_requests": ("Search for pull requests in GitHub repositories using issues search syntax already scoped to is:pr",
                             SEARCH, ["query"]),
}
REACTIONS = {"+1": 0, "-1": 0, "confused": 0, "eyes": 0, "heart": 0, "hooray": 0, "laugh": 0, "rocket": 0, "total_count": 0}


def url(args: dict, kind: str, n: int) -> str:
    return f"https://github.com/{args.get('owner', '')}/{args.get('repo', '')}/{kind}/{n}"


def issue(args: dict, i: dict) -> dict:
    """An issue as `issue_read` `get` gives it: labels by name, present only when it has some."""
    out = {k: v for k, v in i.items() if k not in ("comments", "labels")}
    out.update({"author_association": "MEMBER", "html_url": url(args, "issues", i["number"]), "reactions": REACTIONS,
                "has_children": False, "has_parent": False, "closed_by_pull_requests": {"references": [], "total_count": 0}})
    if i["labels"]:
        out["labels"] = i["labels"]
    return out


def pull_as_issue(args: dict, p: dict) -> dict:
    out = {k: p[k] for k in ("number", "title", "body", "user", "created_at", "updated_at")}
    out.update({"state": p["state"], "html_url": url(args, "pull", p["number"]), "author_association": "MEMBER", "assignees": [],
                "reactions": REACTIONS, "has_children": False, "has_parent": False,
                "closed_by_pull_requests": {"references": [], "total_count": 0}})
    if p.get("closed_at"):
        out["closed_at"] = p["closed_at"]
    return out


def missing(args: dict, n) -> ValueError:
    return ValueError(f"failed to get issue: GET https://api.github.com/repos/{args.get('owner')}/{args.get('repo')}/issues/{n}: 404 Not Found []")


def item(args: dict, i: dict) -> dict:
    """An issue as a search result gives it."""
    out = {"number": i["number"], "title": i["title"], "body": i["body"], "state": i["state"], "html_url": url(args, "issues", i["number"]),
           "labels": i["labels"], "user": i["user"], "created_at": i["created_at"], "updated_at": i["updated_at"],
           "comments": len(i["comments"]), "repository_url": f"https://api.github.com/repos/{args.get('owner')}/{args.get('repo')}"}
    if i.get("state_reason"):
        out["state_reason"] = i["state_reason"]
    return out


def tokens(text: str) -> list:
    """Text as GitHub's search reads it: its words and numbers, lower-cased, punctuation dropped,
    so `#9` matches `#9` and not `#90`."""
    return re.findall(r"[a-z0-9]+", text.lower())


def holds(text: list, phrase: list) -> bool:
    """Whether the phrase's tokens appear in `text` one after another."""
    return any(text[i:i + len(phrase)] == phrase for i in range(len(text) - len(phrase) + 1))


def chosen(row: dict, fields) -> dict:
    return {k: v for k, v in row.items() if k in fields} if fields else row


def call(name: str, args: dict):
    if name == "get_me":
        return {**DATA["me"], "profile_url": f"https://github.com/{DATA['me']['login']}"}
    if name == "issue_read":
        n = int(args.get("issue_number") or 0)
        method = args.get("method")
        if n in PULLS and method == "get":
            return {"issue": pull_as_issue(args, PULLS[n]), "method": "get"}
        if n not in ISSUES and n not in PULLS:
            raise missing(args, n)
        i = ISSUES.get(n)
        if method == "get":
            return {"issue": issue(args, i), "method": "get"}
        if method == "get_comments":
            comments = i["comments"] if i else []
            return {"comments": [{**c, "html_url": f"{url(args, 'issues', n)}#issuecomment-{c['id']}", "reactions": REACTIONS} for c in comments],
                    "method": "get_comments"}
        if method == "get_labels":
            labels = [LABELS[name] for name in (i["labels"] if i else [])]
            return {"labels": labels, "method": "get_labels", "totalCount": len(labels)}
        if method == "get_parent":
            return {"method": "get_parent", "parent": None}
        raise ValueError(f"method {method} is not served by this stub")
    if name == "list_issues":
        state = args.get("state")
        wanted = set(args.get("labels") or [])
        rows = [{"number": i["number"], "title": i["title"], "body": i["body"], "state": i["state"].upper(), "labels": i["labels"],
                 "user": {"login": i["user"]["login"]}, "assignees": i["assignees"], "created_at": i["created_at"],
                 "updated_at": i["updated_at"], **({"comments": len(i["comments"])} if i["comments"] else {})}
                for i in ISSUES.values() if (not state or i["state"].upper() == state) and wanted <= set(i["labels"])]
        rows = [chosen(r, args.get("fields")) for r in rows]
        return {"issues": rows, "pageInfo": {"endCursor": "", "hasNextPage": False, "hasPreviousPage": False, "startCursor": ""},
                "totalCount": len(rows)}
    if name == "search_issues":
        named = re.search(r"\brepo:([^/\s]+)/(\S+)", str(args.get("query", "")))
        if named and not args.get("owner"):
            args = {**args, "owner": named.group(1), "repo": named.group(2)}
        words = {w for w in re.findall(r"[a-z]{3,}", str(args.get("query", "")).lower())}
        hits = [i for i in ISSUES.values() if words & set(re.findall(r"[a-z]{3,}", (i["title"] + " " + i["body"]).lower()))]
        return {"incomplete_results": False, "items": [chosen(item(args, i), args.get("fields")) for i in hits], "total_count": len(hits)}
    if name == "search_pull_requests":
        query = str(args.get("query", ""))
        named = re.search(r"\brepo:([^/\s]+)/(\S+)", query)
        if named and not args.get("owner"):
            args = {**args, "owner": named.group(1), "repo": named.group(2)}
        phrases = [tokens(p) for p in re.findall(r'"([^"]*)"', query)]
        rest = re.sub(r'"[^"]*"', " ", query)
        words = [t for w in rest.split() if not re.match(r"^-?[a-z]+:", w, re.I) for t in tokens(w)]
        hits = []
        for p in PULLS.values():
            text = tokens(f"{p['title']}\n{p['body']}\n{p['head']}")
            if all(holds(text, ph) for ph in phrases) and all(w in text for w in words):
                hits.append({"number": p["number"], "title": p["title"], "body": p["body"], "state": p["state"], "draft": p["draft"],
                             "html_url": url(args, "pull", p["number"]), "user": p["user"], "created_at": p["created_at"],
                             "updated_at": p["updated_at"],
                             "pull_request": {"html_url": url(args, "pull", p["number"]), "diff_url": url(args, "pull", p["number"]) + ".diff"}})
        return {"incomplete_results": False, "items": [chosen(h, args.get("fields")) for h in hits], "total_count": len(hits)}
    if name in SEARCHES:
        return searched(name, args)
    raise ValueError(f"unknown tool {name}")


# The two searches onboarding makes before it reads the issues: `search_repositories`, which
# returns the repository its query's `repo:` names, public, on `main`, as the server's minimal
# output gives it, and `search_code`, which finds nothing, so no standard elsewhere covers the
# repository.
SEARCHES = {
    "search_repositories": ("Find GitHub repositories by name, description, readme, topics, or other metadata.",
                            {"query": TEXT, "sort": TEXT, "order": TEXT, "page": NUMBER, "perPage": NUMBER, "minimal_output": {"type": "boolean"}},
                            ["query"]),
    "search_code": ("Fast and precise code search across ALL GitHub repositories using GitHub's native search engine.",
                    {"query": TEXT, "sort": TEXT, "order": TEXT, "page": NUMBER, "perPage": NUMBER}, ["query"]),
}
TOOLS.update(SEARCHES)


def searched(name: str, args: dict) -> dict:
    named = re.search(r"\brepo:([^/\s]+)/(\S+)", str(args.get("query", "")))
    if name == "search_code" or not named:
        return {"total_count": 0, "incomplete_results": False, "items": []}
    owner, repo = named.groups()
    return {"total_count": 1, "incomplete_results": False,
            "items": [{"id": 2001, "name": repo, "full_name": f"{owner}/{repo}", "html_url": f"https://github.com/{owner}/{repo}",
                       "private": False, "fork": False, "archived": False, "default_branch": "main", "open_issues_count": 2,
                       "created_at": "2026-01-05T10:00:00Z", "updated_at": "2026-02-11T08:00:00Z"}]}


def schema(props: dict, required: list) -> dict:
    return {"type": "object", "properties": props, "required": required}


def reply(rid, result=None, error=None) -> None:
    msg = {"jsonrpc": "2.0", "id": rid}
    msg.update({"error": error} if error else {"result": result})
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        req = json.loads(line)
        method, rid, params = req.get("method"), req.get("id"), req.get("params") or {}
        if rid is None:
            continue
        if method == "initialize":
            reply(rid, {"protocolVersion": params.get("protocolVersion", "2025-06-18"),
                        "capabilities": {"tools": {}}, "serverInfo": {"name": "github-mcp-server-stub", "version": "0"}})
        elif method == "ping":
            reply(rid, {})
        elif method == "tools/list":
            reply(rid, {"tools": [{"name": n, "description": d, "inputSchema": schema(p, r)} for n, (d, p, r) in TOOLS.items()]})
        elif method == "tools/call" and "name" not in params:
            reply(rid, error={"code": -32602, "message": "tools/call names no tool"})
        elif method == "tools/call":
            try:
                text, failed = json.dumps(call(params["name"], params.get("arguments") or {})), False
            except (ValueError, TypeError) as e:
                text, failed = str(e), True
            reply(rid, {"content": [{"type": "text", "text": text}], "isError": failed})
        else:
            reply(rid, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    main()
