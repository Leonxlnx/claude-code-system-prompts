# Simplify Skill

> **Type**: Bundled skill (compiled into Claude Code binary)
>
> **Invocation**: `/simplify` or `/simplify focus on [area]`
>
> The `/simplify` command is a built-in skill that performs an automated, multi-agent code review and cleanup pass on recently changed files. It is designed to be run after implementing a feature or fixing a bug, before opening a pull request.

## Availability

This is a **bundled skill**, meaning it ships inside the Claude Code binary and does not require installation. Unlike custom skills placed in `.claude/skills/`, this skill is maintained by Anthropic and updated with Claude Code releases. The exact `SKILL.md` source is compiled into the binary and not publicly accessible.

The following documentation is reconstructed from public documentation, community sources, and behavioral analysis.

## Workflow

### Phase 1: Change Detection

The skill identifies the scope of review by inspecting recent changes:

- If inside a Git repository, runs `git diff` (or `git diff HEAD` for staged changes) to determine what was modified
- If no Git repository is detected, reviews the most recently modified files
- The diff output defines the exact scope of the review

### Phase 2: Three-Agent Parallel Review

Three specialized sub-agents are spawned in parallel, each receiving the full diff for context:

#### Code Reuse Agent

Reviews changes to identify:

- Duplicated logic that could be extracted into shared functions
- Existing utility functions or helpers that should be used instead of new code
- Redundant code blocks and repeated patterns
- Opportunities to refactor into reusable components or modules

#### Code Quality Agent

Evaluates code structure and style:

- Naming consistency and readability
- Function decomposition and control flow clarity
- Compliance with coding standards defined in `CLAUDE.md`
- Code smells such as leaky abstractions, stringly-typed code, unnecessary nesting
- Over-engineering, unnecessary abstractions, or premature optimization ("gold-plating")

#### Efficiency Agent

Analyzes performance and resource usage:

- Unnecessary allocations and redundant computations
- Loops that could be batched or optimized
- N+1 query patterns and inefficient file or network access
- Missed concurrency opportunities
- Unnecessary re-renders (in frontend code)

### Phase 3: Aggregation and Fix Application

Once all three agents complete their reviews:

1. Findings are aggregated and deduplicated
2. False positives or findings not worth addressing are skipped
3. Fixes are applied directly to the codebase
4. A summary of what was changed is reported to the user

## Usage

```
/simplify                              # Review all recent changes
/simplify focus on memory efficiency   # Focus on specific concern
/simplify focus on performance         # Target performance issues
```

## Integration with CLAUDE.md

The effectiveness of `/simplify` depends heavily on the project's `CLAUDE.md` file. The quality agent uses coding standards and preferences defined there to align its suggestions with the team's conventions. Projects with well-defined `CLAUDE.md` files get significantly better results.

## Design Characteristics

| Property | Detail |
|----------|--------|
| **Agent count** | 3 parallel sub-agents |
| **Scope** | Recent changes only (via `git diff`) |
| **Execution** | Agents run in parallel for efficiency |
| **Fix mode** | Automatic application with summary |
| **False positives** | Skipped rather than argued |
| **Customization** | Accepts focus areas as arguments |
| **Dependency** | Reads `CLAUDE.md` for project-specific standards |

## Position in Workflow

The recommended workflow is:

```
Build feature → Run tests → /simplify → Review diffs → Commit
```

This positions `/simplify` as a post-implementation cleanup pass that tightens AI-generated code, which tends toward verbosity. It is not a replacement for human code review but automates the mechanical cleanup portion.

## Related Commands

| Command | Relationship |
|---------|-------------|
| `/init` | Sets up `CLAUDE.md` that `/simplify` reads for standards |
| `/diff` | Preview changes before running `/simplify` |
| `/batch` | For large-scale refactors across entire codebases (alternative to `/simplify` which targets recent changes only) |
