# Ralph: Automated Feature Development

You are executing an automated development cycle for the Threadline project. Your job is to implement the next incomplete feature from the PRD, verify it works, and update the acceptance criteria checkboxes.

## Instructions

### Step 1: Read Current State

1. Read `PRD.md` to understand the project requirements and find incomplete items (marked with `- [ ]`)
2. Read `ARCHITECTURE.md` to understand the project structure and design patterns
3. Identify the **next uncompleted feature** in priority order:
   - Features within a phase should be completed in order (F1.1 before F1.2, etc.)
   - Complete Phase 1 before Phase 2, etc.
   - Within a feature, complete all acceptance criteria before moving to the next feature

### Step 2: Implement the Feature

1. Focus on **ONE feature** or a small set of related acceptance criteria per cycle
2. Follow the patterns established in ARCHITECTURE.md
3. Write clean, minimal code that satisfies the acceptance criteria
4. Add `from __future__ import annotations` to any new Python files
5. Do NOT over-engineer or add features beyond what's specified

### Step 3: Verify Acceptance Criteria

For each acceptance criterion you implement:

1. **Test it actually works** - run the code, check the output
2. If it involves a CLI command, run the command and verify the output
3. If it involves data storage, verify the data is stored correctly
4. Only mark complete if you have **verified** it works

### Step 3b: Run Regression Tests

After implementing a feature, run the regression test suite to ensure existing functionality still works:

1. Run `pytest tests/` to execute all regression tests
2. All existing tests must pass before marking any acceptance criteria complete
3. If tests fail, fix the regression before continuing
4. If you add a new CLI command or modify existing behavior, add or update tests in `tests/`

**Test requirements:**
- Tests use temp directories (never touch real `~/.threadline/`)
- Tests should be fast and isolated
- Each test verifies one specific behavior
- Use fixtures for common setup (temp home, sample files)

### Step 4: Update the PRD

After verifying each criterion:

1. Edit `PRD.md` to change `- [ ]` to `- [x]` for completed items
2. If an item only partially works, leave it unchecked and add a note
3. Be honest - only check items that truly work

### Step 5: Summarize, Commit code with git, and Exit

After completing **one feature** (or making meaningful progress on a larger feature):

1. Provide a brief summary of what was implemented
2. List which acceptance criteria were completed
3. Note any issues or blockers encountered
4. Create logical commits for all your work;
   - git commits should have the title of the PRD section title, and include the check boxes completed in the body
   - for fixes, they should prepend the commit title with "fix:"
5. Exit cleanly - `git commit -m` your work, and do not continue to the next feature

## Important Rules

- **One feature per cycle** - Focus and complete, don't spread thin
- **Verify before marking complete** - Actually test the functionality
- **Run regression tests** - `pytest tests/` must pass before marking complete
- **Follow existing patterns** - Check how similar features were implemented
- **No scope creep** - Implement exactly what the acceptance criterion says
- **Be honest about progress** - Don't mark items complete if they're not working

## Priority Order for Remaining Work

Based on the PRD phases:

1. **F1.10**: Regression Tests - set up test infrastructure and basic CLI tests
2. **Phase 1b**: Entry Classification (F1.5), OCR (F1.2) - complete remaining Phase 1 items
3. **Phase 2**: TUI Browser - Entry list, detail view, tagging, filtering
4. **Phase 3**: Theme extraction, similarity search
5. **Phase 4**: Export, maintenance commands

## Context Files

- `PRD.md` - Product requirements with acceptance criteria checkboxes
- `ARCHITECTURE.md` - Technical design and project structure
- `src/threadline/` - Source code
- `tests/` - Regression tests (run with `pytest tests/`)
- `pyproject.toml` - Dependencies and project config

## Example Workflow

```
1. Read PRD.md → Find "F1.5: Entry Classification" is next incomplete feature
2. Read ARCHITECTURE.md → Understand where classifier code should go
3. Check existing code → See how embedder.py was implemented
4. Implement core/classifier.py following the pattern
5. Wire it into ingest/pipeline.py
6. Test: run `threadline ingest` on a test file
7. Verify entries have entry_type populated
8. Run `pytest tests/` → Ensure all regression tests pass
9. Update PRD.md checkboxes for completed criteria
10. Summarize: "Implemented local classification using bart-large-mnli"
11. Exit
```

## Start Now

Begin by reading the PRD to find the next incomplete feature, then proceed with implementation.
