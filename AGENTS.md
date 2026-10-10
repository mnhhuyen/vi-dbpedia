## Subagent rules

These rules apply only WHEN delegation is already allowed (the user asked, or ultra mode).
They do not by themselves request spawning subagents.

Delegate only when the task has 2+ independent parts that can run in parallel, each large enough.
Small work, or work that needs the full history (hard design/debug): do it yourself.
At most 2 subagents at a time. Subagents never spawn their own subagents.

Before spawning, write the shared contracts to disk: types/interfaces, function signatures, data/API formats,
shared constants. The brief must point to these files; subagents read them instead of assuming.

When calling spawn_agent, always set model, reasoning_effort and fork_turns explicitly:

| Work type | model | reasoning_effort | fork_turns |
|---|---|---|---|
| Explore, read code, search files, gather info | gpt-6-luna | medium | "none" |
| Write a module/tests with a clear spec | gpt-6-astra | high | "none" |
| Work that needs the recent discussion | gpt-6-astra | high | "2" |

The brief (message) must include:
1. Goal. 2. Context: stack, paths, constraints.
3. Files it may create/edit; each subagent gets its own files, no overlap.
4. Done criteria and how to self-check (command to run, expected result).
5. What NOT to do.

Coordination:
- A subagent finishes the whole job, self-checks, then reports ONCE (max 15 lines):
  files changed, how it was checked, open issues.
- The main agent waits with wait_agent; no status polling, no back-and-forth messages.
- Do not re-read or redo work a subagent already reported; only check the issues it lists.
- Send followup_task only when the result is actually wrong.

## Code style rules

- Split code into multiple files, each under ~300 lines, one statement per line.
- Applies to EVERY file type (JS, CSS, HTML), not just JS:
  - CSS: one block per selector, one property per line; media queries on their own lines, indented; never put several rules on one line.
  - HTML: one block-level tag (div, section, button, ...) per line, indented by depth; no long inline CSS/JS in HTML.
  - No line longer than ~120 characters (except data strings that cannot be split).
- Several files may be written in one tool call (apply_patch accepts multiple files per call).

## Publishing

Do not create, deploy or publish sites/hosting (Sites or any other service) unless the user explicitly asks to publish.
Build and run locally only. Keep source code out of the build output folder (e.g. never write source into dist/).
