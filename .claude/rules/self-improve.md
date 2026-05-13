---
description: Self-improvement loop for tools, skills, and agents
globs: .claude/**/*
---

# Self-Improvement Rule

When a tool, skill, or agent fails or produces suboptimal results during your work, and you suspect the issue lies in the tool/skill/agent itself (not in user input or environment), you MUST:

## Detection Criteria

Trigger self-improvement when ANY of these occur:

1. **Tool failure**: A tool call errors out or returns unexpected/empty results, and the cause appears to be in the tool's implementation or configuration — not in the arguments you passed.
2. **Skill misbehavior**: A skill triggers incorrectly (false positive/negative), produces poor guidance, or its instructions are ambiguous/incomplete.
3. **Agent failure**: A subagent fails to complete its task, returns irrelevant results, or gets stuck — and the issue seems structural (bad prompt, wrong tool access, missing context).
4. **Improvement opportunity**: You notice a tool/skill/agent could be meaningfully improved — better error handling, clearer instructions, missing edge cases, or a workflow gap.

## Action

1. **Do NOT stop your main task.** Note the issue, then continue with a workaround if possible.
2. **Launch a background subagent** (using the Agent tool with `run_in_background: true`) to investigate and fix the issue:

   ```
   Agent(
     subagent_type: "general-purpose",
     description: "Improve <tool/skill/agent name>",
     run_in_background: true,
     prompt: """
     A tool/skill/agent needs improvement. Here's the context:

     **What failed or needs improvement:** <describe the issue>
     **File location:** <path to the skill/agent/tool definition>
     **Expected behavior:** <what should have happened>
     **Actual behavior:** <what actually happened>

     Instructions:
     1. Read the relevant file(s) to understand the current implementation
     2. Identify the root cause or improvement opportunity
     3. Make the fix/improvement directly — edit the file(s)
     4. Keep changes minimal and focused on the specific issue
     5. Do NOT break existing functionality
     6. If the fix requires user input or is risky, describe what you'd change but don't edit
     """
   )
   ```

3. **Resume your main task** immediately — don't wait for the subagent to finish.
4. **When the subagent completes**, briefly inform the user what was improved (one sentence).

## Scope

This applies to:
- Skills in `.claude/skills/` (SKILL.md files and their supporting resources)
- Agents in `.claude/agents/` (if any)
- Rules in `.claude/rules/` (including this one — yes, it can improve itself)
- Scripts in `.claude/` or `scripts/` that are invoked by skills/tools

This does NOT apply to:
- Built-in Claude Code tools (Read, Write, Bash, etc.) — you can't modify those
- External MCP servers — flag the issue to the user instead
- User code outside `.claude/` — that's the user's domain, not self-improvement

## Guidelines

- **Be conservative**: Only trigger for genuine issues, not minor style preferences.
- **Be transparent**: Always tell the user when you've launched a self-improvement subagent.
- **Don't loop**: If a self-improvement attempt itself fails, flag it to the user — don't recursively try to fix the fixer.
- **Track improvements**: When you fix something, add a brief comment in the file noting what was changed and why (as a code comment or markdown note, as appropriate).