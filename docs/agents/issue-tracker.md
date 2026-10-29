# Issue tracker: GitHub

Issues and specs live in GitHub Issues for `alexelite/ha-virtual-climate`. Use the `gh` CLI from this repository.

## Operations

- Create: `gh issue create --title "..." --body-file <path>`. Write multiline bodies to a temporary file.
- Read: `gh issue view <number> --json number,title,body,labels,comments`.
- List: `gh issue list --state open --json number,title,body,labels,comments`, with appropriate state and label filters.
- Comment: `gh issue comment <number> --body-file <path>`.
- Apply or remove labels: `gh issue edit <number> --add-label "..."` or `--remove-label "..."`.
- Close: `gh issue close <number>`; post any detailed explanation with the comment operation first.
- Read the label mapping in `docs/agents/triage-labels.md` before choosing triage labels.

When a skill says "publish to the issue tracker", create a GitHub issue. When it says "fetch the relevant ticket", read that GitHub issue.

## Pull requests as a triage surface

**PRs as a request surface: no.**

GitHub issues and pull requests share one number space. Resolve an ambiguous number with `gh pr view <number>`, falling back to `gh issue view <number>`.

## Wayfinding operations

For the wayfinder skill, the map is one issue with child issues as tickets.

- Map: one issue labelled `wayfinder:map`, containing Notes, Decisions-so-far, and Fog.
- Child: link each ticket to the map as a native GitHub sub-issue when supported. Otherwise, add a task-list link to the map body and `Part of #<map>` at the top of the child body.
- Ticket labels: `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling`, or `wayfinder:task`. Ensure required labels exist before using them.
- Blocking: use native GitHub issue dependencies when supported. Obtain numeric database IDs with `gh api repos/alexelite/ha-virtual-climate/issues/<number> --jq .id`. Add a dependency with `gh api --method POST repos/alexelite/ha-virtual-climate/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-database-id>`. Otherwise, put `Blocked by: #<number>` at the top of the ticket body.
- Frontier: select the first open child in map order with no assignee and no open blocker.
- Claim: `gh issue edit <number> --add-assignee @me`.
- Resolve: comment with the answer, close the ticket, and append a concise finding plus a link to the map's Decisions-so-far.
