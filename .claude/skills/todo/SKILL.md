---
name: todo
description: Manage the project TODO list. Use when the user says "todo", "show todos", "what's left", "update todos", "add todo", or "mark done".
argument-hint: "[show|add|done|clean] [task description]"
---

# TODO Tracker

Manage the project TODO file for tracking multi-step work.

## When This Skill Applies

- User asks to see, add, update, or clean TODO items
- Starting a new multi-step task that needs tracking

## Workflow

### `/todo show`

Read and display `TODO.md` at the project root. Summarize: how many open, how many done, any blocked items.

### `/todo add <description>`

Add a new `- [ ]` item to the appropriate section of `TODO.md`. If no section fits, create one under "Remaining Work".

### `/todo done <task keyword>`

Find the matching task by keyword and mark it `[x]`.

### `/todo clean`

Remove all completed (`[x]`) items.

## TODO File Location

`TODO.md` at the project root.
