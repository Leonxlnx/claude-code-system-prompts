[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/leonxlnx-agentic-ai-prompt-research-badge.png)](https://mseep.ai/app/leonxlnx-agentic-ai-prompt-research)

# Claude Code System Prompts

A research project exploring how modern agentic AI coding assistants work under the hood. This repository contains our best understanding of the prompt architecture, agent coordination patterns, and security mechanisms that power tools like Claude Code.

Everything here is based on behavioral observation, output analysis, community discussions, and publicly shared information. These are reconstructed approximations, not verbatim copies. The actual implementation may differ significantly.

## What This Project Is

This is an educational deep-dive into the design patterns behind agentic coding assistants. We analyze how these systems:

- Assemble dynamic system prompts at runtime
- Coordinate multiple specialized sub-agents
- Classify and auto-approve tool calls safely
- Manage context windows through intelligent compaction
- Handle memory, skills, and user preferences

The goal is to help AI engineers, researchers, and builders learn from these architectural patterns and apply them in their own projects.

## What This Project Is Not

This is **not** a leak, dump, or direct copy of any proprietary system. The prompts documented here are our best reconstructions based on observable behavior. They represent one interpretation of how these systems likely work.

## Documented Patterns

### Core Identity

| # | Pattern | Description |
|---|---------|-------------|
| 01 | [Main System Prompt](prompts/01_main_system_prompt.md) | How the master prompt is dynamically assembled from modular sections |
| 02 | [Simple Mode](prompts/02_simple_mode.md) | Minimal prompt variant for lightweight operation |
| 03 | [Default Agent Prompt](prompts/03_default_agent_prompt.md) | Base instructions inherited by all sub-agents |
| 04 | [Cyber Risk Instruction](prompts/04_cyber_risk_instruction.md) | Security boundaries between authorized and prohibited actions |

### Orchestration

| # | Pattern | Description |
|---|---------|-------------|
| 05 | [Coordinator System Prompt](prompts/05_coordinator_system_prompt.md) | Multi-worker orchestration with phased workflows |
| 06 | [Teammate Prompt Addendum](prompts/06_teammate_prompt_addendum.md) | Communication protocols for multi-agent collaboration |

### Specialized Agents

| # | Pattern | Description |
|---|---------|-------------|
| 07 | [Verification Agent](prompts/07_verification_agent.md) | Adversarial testing agent that validates implementations |
| 08 | [Explore Agent](prompts/08_explore_agent.md) | Read-only codebase exploration with no-modify constraints |
| 09 | [Agent Creation Architect](prompts/09_agent_creation_architect.md) | Generates new agent configurations from requirements |
| 10 | [Status Line Setup Agent](prompts/10_statusline_setup_agent.md) | Terminal status line configuration across shells |

### Security and Permissions

| # | Pattern | Description |
|---|---------|-------------|
| 11 | [Permission Explainer](prompts/11_permission_explainer.md) | Risk assessment before tool approval |
| 12 | [Auto Mode Classifier](prompts/12_yolo_auto_mode_classifier.md) | Multi-stage security classifier for autonomous tool execution |

### Tool Descriptions

| # | Pattern | Description |
|---|---------|-------------|
| 13 | [Tool-Specific Prompts](prompts/13_tool_prompts.md) | How individual tools (Bash, Edit, Agent, etc.) describe themselves |

### Utility Patterns

| # | Pattern | Description |
|---|---------|-------------|
| 14 | [Tool Use Summary](prompts/14_tool_use_summary.md) | Generating concise labels for completed tool batches |
| 15 | [Session Search](prompts/15_session_search.md) | Semantic search across past conversation sessions |
| 16 | [Memory Selection](prompts/16_memory_selection.md) | Selecting relevant memory files for query context |
| 17 | [Auto Mode Critique](prompts/17_auto_mode_critique.md) | Reviewing user-written classifier rules |
| 20 | [Session Title](prompts/20_session_title.md) | Lightweight title generation for session management |
| 29 | [Agent Summary](prompts/29_agent_summary.md) | Background progress updates for sub-agents |
| 30 | [Prompt Suggestion](prompts/30_prompt_suggestion.md) | Predicting likely user follow-up commands |

### Context Window Management

| # | Pattern | Description |
|---|---------|-------------|
| 21 | [Compact Service](prompts/21_compact_service.md) | Conversation summarization strategies for long sessions |
| 22 | [Away Summary](prompts/22_away_summary.md) | Brief session recaps for returning users |

### Dynamic Behaviors

| # | Pattern | Description |
|---|---------|-------------|
| 18 | [Proactive Mode](prompts/18_proactive_mode.md) | Autonomous background operation with pacing controls |
| 23 | [Chrome Browser Automation](prompts/23_chrome_browser_automation.md) | Browser extension integration patterns |
| 24 | [Memory Instruction](prompts/24_memory_instruction.md) | Hierarchical memory loading and override semantics |

### Skill Patterns

| # | Pattern | Description |
|---|---------|-------------|
| 19 | [Simplify Skill](prompts/19_simplify_skill.md) | Multi-agent parallel code review pattern |
| 25 | [Skillify Skill](prompts/25_skillify.md) | Interview-based skill creation workflow |
| 26 | [Stuck Skill](prompts/26_stuck_skill.md) | Session diagnostic and recovery patterns |
| 27 | [Remember Skill](prompts/27_remember_skill.md) | Memory organization and promotion workflow |
| 28 | [Update Config Skill](prompts/28_update_config_skill.md) | Configuration management patterns |

## Architectural Observations

### Dynamic Prompt Assembly

Based on our analysis, the system prompt appears to be assembled through a pipeline of modular builders:

```
Prompt Assembly Pipeline
    |
    |   Cacheable Prefix (stable across sessions)
    |-- Identity and safety instructions
    |-- Permission and hook configuration
    |-- Code style and error handling rules
    |-- Tool preferences and usage patterns
    |-- Tone, style, and output rules
    |
    |   Cache Boundary
    |
    |   Dynamic Suffix (changes per session)
    |-- Available agents and skills
    |-- Memory file contents
    |-- Environment context (OS, directory, git state)
    |-- Language and output preferences
    |-- Active MCP server instructions
    |-- Context window management directives
```

### Security Classification

The auto-approval system appears to use a multi-stage approach:

1. A base classifier with predefined rules for safe and unsafe operations
2. User-configurable overrides that can extend or restrict the defaults
3. A fast first pass, with extended reasoning as fallback for ambiguous cases

### Memory Hierarchy

```
Loading Order (earliest = lowest priority):
    |
    |-- Enterprise/managed configuration
    |-- User global preferences
    |-- Project-level instructions (shared)
    |-- Project rules directory
    |-- Local overrides (private, not committed)
    |
    |   Supports transitive file inclusion
    |   Conditional injection via path-based filtering
```

## Use Cases

This research is useful for:

- **AI engineers** building their own agentic coding tools
- **Prompt engineers** studying production-grade prompt architectures
- **Security researchers** understanding how autonomous AI tools manage permissions
- **Students and educators** learning about multi-agent system design

## Repository Structure

```
claude-code-system-prompts/
    README.md
    prompts/
        01-30 documented patterns (see catalog above)
```

## Disclaimer

This is an independent research project. All content represents our analysis and approximations based on publicly observable behavior. This project is not affiliated with, endorsed by, or connected to Anthropic. All trademarks belong to their respective owners. If any content owner has concerns, please open an issue and we will address it promptly.
