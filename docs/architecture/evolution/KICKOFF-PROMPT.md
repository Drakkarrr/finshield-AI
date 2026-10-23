# KICKOFF PROMPT — paste this into a fresh agent session

This is the short message you paste into Claude Code / Qwen3-Max in Qoder IDE to start a session.
The agent will read the master prompt and the progress ledger itself.

---

## PROMPT (copy from here)

```
You are starting a session of the FinShield AI implementation mission.

1. Read docs/architecture/evolution/PROGRESS.md first — that is the ledger from the previous
   session. Find the first unchecked slice. If it does not exist yet, this is session 0.

2. Read docs/architecture/evolution/MASTER-PROMPT.md in full and follow it exactly. In particular:
   - Section 0 (ORIENTATION): read the files listed in order, verify the baseline test is green,
     and create PROGRESS.md from the tracking table in llm-implementation-briefs.md if it does not
     exist.
   - Section 10 (YOUR FIRST MESSAGE): your first reply to me must be the five items listed there
     (where the ledger says you are, baseline test output, plan for this session, drift found,
     rulings challenged). Under 30 lines.
   - Then proceed per Section 3 (EXECUTION PROTOCOL): plan, implement, test, self-audit, commit,
     update the ledger, write the handoff report, stop.

3. Do NOT write any code until your §10 first message is complete and I have seen it.

4. Do NOT push, open a PR, amend a published commit, or rewrite git history without my explicit
   instruction in this session.

5. If you hit anything you cannot resolve in this session (destructive operation, ruling contradicted
   by code, dependency you cannot install, test you cannot pass after two genuine attempts, slice
   scope > 3x the brief), stop and ask. Never stub, skip, xfail, or swallow the error.

Begin.
```

## PROMPT (end)

---

## How to use this

1. Open the repo in Qoder IDE.
2. Start a new Claude Code or Qwen3-Max session at the repo root.
3. Paste the block above.
4. The agent will:
   - read the ledger,
   - read the master prompt,
   - reply with its §10 first message (orientation + plan),
   - then work through one phase,
   - then update the ledger and stop.
5. When it stops, review its handoff report. If the work is good, start a new session and paste the
   same kickoff prompt again — it will pick up from the next unchecked slice.

## Variants

**Force a specific phase** (instead of the ledger's next slice):
append to the kickoff prompt:
  "Start at phase P2, slice S2.1. Do not read PROGRESS.md to locate — begin at S2.1."

**Skip a ruling** (if you disagree with one of D1-D13):
append:
  "Override ruling D5: use hand-rolled primitives on the existing tokens instead of Radix/shadcn.
   Adjust S5.2 and S5.3 accordingly and note the change in your report."

**Run a specific slice only** (for a quick fix):
append:
  "Do only slice S0.5. Do not touch any other slice. Report when done."

**Resume after a failure**:
append:
  "The last session left PROGRESS.md in an inconsistent state. Re-verify every checked box by
   running its test command. Revert any that do not reproduce, then continue from the first
   genuinely closed slice."
