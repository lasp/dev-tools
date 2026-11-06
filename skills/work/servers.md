# When a server is missing or failing

Every skill and agent that reads GitHub, Jira or Confluence through an MCP server says the same
four things when that server is not there or a call to it fails, so a person who has never set one
up knows what happened and what to do. The plugin root this file writes as `<plugin root>` is the
one the citing skill names.

## Which case it is

- **Not connected**: `ToolSearch` finds none of the server's tools. Nothing is configured, or
  Claude Code could not start it.
- **Not configured for this service**: the Atlassian server is connected, but `ToolSearch` finds
  none of the one service's tools, `jira_` or `confluence_`. The server leaves out a service whose
  URL or token it was not given, so its calls never fail: they are not there. The fix is that
  service's URL and token in the server's setup.
- **Connected, but the call failed**: the tools resolve and a call returns an error. Name the
  likely causes for that error, never one as certain:
  - an error on every call (`401`, "Bad credentials", nothing returned for anything) is usually an
    expired or missing token;
  - an error, an empty result or a `404` on one repository, Jira project or Confluence space, while
    others read, is usually the token's account lacking access to it. Jira and Confluence tokens
    read what their account can, and two people's tokens, or one person's two servers, can reach
    different projects and spaces, so a ticket or page another person reads may be out of this
    token's reach.

Say which, with the error verbatim in the second case. Never diagnose beyond this, never retry on
another server, and never fall back on your own.

## The message

Four parts, in this order, in two or three lines:

1. **Which server**: GitHub, or the Atlassian server for Jira or Confluence, and which case.
2. **What is lost**: what this step would have read or written, named concretely ("the
   repository's visibility and the search for repositories that use it", "the ticket's text").
3. **Whether the run goes on**: a skill stops only at the step that needs the server; elsewhere it
   goes on without what was lost and says so. When it stops, say what the person can give instead.
4. **How to fix it**: `/lasp-dev:quickstart` shows which servers this machine has and the fix
   for each; the plugin's README, `<plugin root>/README.md`, "MCP servers", says how each is set
   up and, under "When a server is missing or failing", how to check it; and Claude Code's guide to MCP servers is https://code.claude.com/docs/en/mcp. For a
   connected server whose calls all fail, refreshing its token and restarting Claude Code from a
   shell that has it is the usual fix; for one item out of reach, access for the token's account,
   or a token from an account that has it. `/mcp` shows each server's status. Then the alternative this
   plugin takes, where the step has one: for GitHub, the `gh` CLI when the person says so (`gh
   auth status` shows whether it is signed in), except at a step that needs the server's review
   threads, which `gh` cannot give; for Jira or Confluence, pasted text or a file.

For example, onboarding with no GitHub server:

> The GitHub server is not connected, so onboarding goes on without searching your organization
> for a shared standard or for the repositories that use this one, and without the repository's
> visibility. `/lasp-dev:quickstart` shows how to connect it, as do the plugin README's "MCP
> servers" and https://code.claude.com/docs/en/mcp.

Where the tracker is GitHub's, the ticket is an issue and GitHub is the server that reads it, in the
same four parts:

> The GitHub server is connected, but reading issue #59 failed: `404 Not Found`. Other GitHub
> reads work, so your token's account most likely cannot see the issue tracker's repository. Work
> goes on without its state and labels, routing it as a ticket whose status is unknown;
> `/mcp` shows the server's status, and the README's "MCP servers" says how to give the token
> access. Paste the issue's text here to go on without it.

And a Jira ticket read that failed:

> The Atlassian server is connected, but reading PROJ-42 failed: `403 Forbidden`. Other Jira
> reads work, so your token's account most likely cannot see the PROJ project; an expired token
> would fail everywhere. Ask a project admin for access, or use a token from an account that has
> it (README "MCP servers" says where tokens come from, and `/mcp` shows the server's status).
> Paste the ticket's text here to go on without it.

## Agents

An agent never asks. It returns the first three parts to its caller, as one line beginning
`<server>: not connected` or `<server>: failed: <error, verbatim>`, followed by what it could not
do, and ends. The calling skill tells the person, adding the fix.

## Once per run

Say it once per server per run, at the first step that needs the server; a later step that skips
for the same reason says so in a few words ("no GitHub server, as above").
