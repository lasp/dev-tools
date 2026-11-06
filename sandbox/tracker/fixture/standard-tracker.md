# The widgets tracker

The facts `using-jira` reads about the widgets Jira project; everything else about tickets is the
plugin's.

## The project

PROJ, at `https://jira.example.com/browse/PROJ-NNNN`, is the tracker of record for the widgets
repository.

## Fields

| Field | How it is used |
| --- | --- |
| Issue type | Task, Bug, Improvement, Epic |
| Status | New, To Do, Upcoming, Under Development, In Review, Done, Abandoned |
| Priority | Normal by default; Minor, Major, Critical |
| Components | Inventory, Loader, Restock; a drafted ticket always proposes one |
| Epic Link | `customfield_10014`, the epic's key |
| Due date | Set only when a month is asked for |
| Links | Relates; Blocks |
| Story Points | `customfield_10016`, the estimate |

## The workflow

New, then To Do, then Upcoming, Under Development, In Review, to Done or Abandoned. The roles sit
on New (filed), To Do (approved), Under Development (implementation), Done (finished) and
Abandoned (abandoned), as the profile's `jira.roles` states them.

## Estimates

Story points on a Fibonacci scale (1, 2, 3, 5, 8, 13), the median effort. The reference tasks sit
at 2 and 5.

## JQL that works

- Open work: `project = PROJ AND statusCategory != Done`
- Text across summary and description: `project = PROJ AND text ~ "by part"`
