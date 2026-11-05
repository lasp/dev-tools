#!/usr/bin/env python3
"""A read-only stand-in for the mcp-atlassian server, serving the fixed Jira project in
`jira.json` beside it over stdio, so a scenario reads a ticket, a search and the components with
no Jira. Its name holds `mcp-atlassian`, so `run.py` gives it the Atlassian rules, and it is
listed with `--read-only` and `READ_ONLY_MODE=true`, which it honors by having no write tools.

    {"command": "python3", "args": ["-I", "<this file>", "--read-only"], "env": {"READ_ONLY_MODE": "true"}}

`jira_search` returns the description as stored, in wiki markup; `jira_get_issue` returns a
rough Markdown conversion of it, as the real server does. A search naming keys (`key = A`,
`key in (A, B)`) returns those issues; any other query returns every issue in the project, Done
ones included, since no clause beyond the key is read. A key the project does not hold is an
error result. Confluence holds no page. Stdlib only.
"""

import json
import re
import sys
from pathlib import Path

DATA = json.loads((Path(__file__).with_name("jira.json")).read_text())
ISSUES = {i["key"]: i for i in DATA["issues"]}

TOOLS = {
    "jira_get_issue": ("A Jira issue's fields, comments and links, its description converted to Markdown.",
                       {"issue_key": "string", "fields": "string", "expand": "string", "comment_limit": "integer"}, ["issue_key"]),
    "jira_search": ("Issues matching a JQL query, with the fields asked for, the description as stored.",
                    {"jql": "string", "fields": "string", "limit": "integer", "start_at": "integer"}, ["jql"]),
    "jira_get_project_components": ("A project's components.", {"project_key": "string"}, ["project_key"]),
    "jira_get_project_issue_types": ("A project's issue types.", {"project_key": "string"}, ["project_key"]),
    "jira_get_all_projects": ("Every project the account can read.", {}, []),
    "jira_search_fields": ("Fields whose name matches a keyword.", {"keyword": "string", "limit": "integer"}, []),
    "jira_get_transitions": ("The transitions an issue can take.", {"issue_key": "string"}, ["issue_key"]),
    "confluence_search": ("Confluence pages matching a query.", {"query": "string", "limit": "integer"}, ["query"]),
    "confluence_get_page": ("A Confluence page.", {"page_id": "string", "title": "string", "space_key": "string"}, []),
}


def markdown(text: str) -> str:
    text = re.sub(r"(?m)^# ", "1. ", text)
    text = re.sub(r"(?m)^h([1-6])\. ", lambda m: "#" * int(m.group(1)) + " ", text)
    text = re.sub(r"(?m)^\* ", "- ", text)
    return re.sub(r"\{\{(.+?)\}\}", r"`\1`", text)


def issue(i: dict, converted: bool) -> dict:
    out = {k: v for k, v in i.items() if k != "description"}
    out["description"] = markdown(i["description"]) if converted else i["description"]
    return out


def call(name: str, args: dict):
    if name == "jira_get_issue":
        key = str(args.get("issue_key", "")).upper()
        if key not in ISSUES:
            raise ValueError(f"Issue Does Not Exist: {key}")
        return issue(ISSUES[key], converted=True)
    if name == "jira_search":
        jql = args.get("jql", "")
        named = re.findall(r"\b(?:key|issuekey)\s*(?:=\s*[A-Z]+-\d+|in\s*\([^)]*\))", jql, re.I)
        keys = re.findall(r"[A-Z]+-\d+", " ".join(named), re.I)
        found = [ISSUES[k.upper()] for k in keys if k.upper() in ISSUES] if keys else list(ISSUES.values())
        found = found[: int(args.get("limit") or 50)]
        return {"total": len(found), "start_at": 0, "max_results": len(found), "issues": [issue(i, converted=False) for i in found]}
    if name == "jira_get_project_components":
        return DATA["components"]
    if name == "jira_get_project_issue_types":
        return DATA["issue_types"]
    if name == "jira_get_all_projects":
        return [{"key": DATA["project"], "name": DATA["project_name"]}]
    if name == "jira_search_fields":
        kw = str(args.get("keyword", "")).lower()
        return [f for f in DATA["fields"] if kw in f["name"].lower()]
    if name == "jira_get_transitions":
        return DATA["transitions"]
    if name == "confluence_search":
        return []
    if name == "confluence_get_page":
        raise ValueError("Page not found")
    raise ValueError(f"unknown tool {name}")


def schema(props: dict, required: list) -> dict:
    return {"type": "object", "properties": {k: {"type": t} for k, t in props.items()}, "required": required}


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
                        "capabilities": {"tools": {}}, "serverInfo": {"name": "mcp-atlassian-stub", "version": "0"}})
        elif method == "ping":
            reply(rid, {})
        elif method == "tools/list":
            reply(rid, {"tools": [{"name": n, "description": d, "inputSchema": schema(p, r)} for n, (d, p, r) in TOOLS.items()]})
        elif method == "tools/call" and "name" not in params:
            reply(rid, error={"code": -32602, "message": "tools/call names no tool"})
        elif method == "tools/call":
            try:
                text, failed = json.dumps(call(params["name"], params.get("arguments") or {}), indent=2), False
            except ValueError as e:
                text, failed = f"Error: {e}", True
            reply(rid, {"content": [{"type": "text", "text": text}], "isError": failed})
        else:
            reply(rid, error={"code": -32601, "message": f"method not found: {method}"})


if __name__ == "__main__":
    main()
