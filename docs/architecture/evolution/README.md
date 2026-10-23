# FinShield AI — Architecture Evolution Pack

Generated 2026-10-23 by the Qoder `architecture-visualization` plugin (`evolution-planner` + `c4model` + `graphviz`) with `design-review` lenses for the frontend track.

**One-line answer:** FinShield AI is a working prototype (68 real routes, 65 passing tests, real auth, real case and SAR/STR persistence) wrapped in production-grade documentation. The work needed is not "build more" — it is *connect what already exists, replace what is random, version what is asserted, and stop documenting what is not true*.

## Reading order

| # | File | Read it when you want to… |
|---|---|---|
| 1 | [evolution-summary.md](./evolution-summary.md) | Understand the situation and the argument for the sequencing. **Start here.** |
| 2 | [gap-map.dot](./gap-map.dot) | See every capability colour-coded: wired / built-but-unreachable / stub / absent. |
| 3 | [decision-map.md](./decision-map.md) | Rule on the 12 open decisions. Five of them gate real work. |
| 4 | [migration-roadmap.md](./migration-roadmap.md) | See the 37 slices across 7 phases with effort, risk, reversibility and validation signals. |
| 5 | [llm-implementation-briefs.md](./llm-implementation-briefs.md) | **Copy-paste briefs.** One self-contained brief per phase, for driving a single phase yourself. |
| 6 | [MASTER-PROMPT.md](./MASTER-PROMPT.md) | **Hand the whole mission to an agent.** Self-resuming orchestrator prompt with the 12 decisions pre-ruled, per-phase gates, gap-closure greps and a 25-point market-readiness definition. |
| 7 | [PROGRESS.md](./PROGRESS.md) | The ledger the master prompt reads and writes — the resume point across sessions. |
| 8 | [architecture-evolution.dot](./architecture-evolution.dot) | See which slice unblocks which. |
| 9 | [current-vs-target.dsl](./current-vs-target.dsl) | Show the current vs proposed system to another person. |
| 10 | [evidence.md](./evidence.md) | Check any claim against its `path:line` citation. `✔ verified` rows were re-checked directly against source. |

**Which do I paste?** Use [MASTER-PROMPT.md](./MASTER-PROMPT.md) if you want an agent to own the whole roadmap across sessions. Use [llm-implementation-briefs.md](./llm-implementation-briefs.md) if you want to drive one phase yourself and keep tighter control. They share the same slice ids, so you can switch between them mid-flight.

## Diagram sources and how to render them

Both diagram sources are text and are the canonical artefacts — any SVG/PNG is derived and must not be hand-edited.

- `current-vs-target.dsl` — Structurizr DSL. Open with the Qoder Canvas DSL viewer, or `structurizr-cli export -workspace current-vs-target.dsl -format plantuml`. Three views are defined: `L1-context`, `L2-current-vs-target`, `L3-detection-pipeline`.
- `gap-map.dot`, `architecture-evolution.dot` — Graphviz DOT. Open with the Qoder Canvas DOT viewer, or `dot -Tsvg gap-map.dot -o gap-map.svg`. Graphviz is **not installed** on this machine (`which dot` → not found), so neither file has been rendered here; both were syntax-checked programmatically (balanced braces and quotes, every node id referenced in an edge carries a label).

Colour conventions are consistent across all three diagram sources: green = implemented and wired · amber dashed = built but not wired (dead code) · orange = stub/placeholder · red = absent · purple dashed = target/proposed · grey dashed = deprecated.

## Regenerating this pack

The analysis is evidence-driven, so regenerate it rather than editing it when the code moves:

1. Re-run the audits (backend implementation, frontend, ops/security) against current `HEAD`.
2. Update [evidence.md](./evidence.md) first — every other file cites it.
3. Re-derive the gap map and roadmap from the updated evidence.
4. For a drift check only, use the `architecture-visualization:architecture-health` skill, which diffs these artefacts against code, config and runtime evidence and flags stale claims.

Regenerate after **Phase 0** lands (docs reconciled, secrets untracked, CI fixed, health probes real, two latent bugs fixed) — that phase changes the evidence base more than any other.

## Known limitations of this analysis

- Line numbers are as of commit `91e4de8` (2026-10-23). Re-locate by symbol name if they drift.
- Rows in `evidence.md` marked `agent` came from a code-search subagent and were not each individually re-opened. The ~40 rows marked `✔ verified` were re-checked directly during this analysis, including every ship-blocker: the tracked `backend/.env`, the unreachable `/export` route, the `import math` NameError, the hardcoded health map, the `random.uniform` in the scoring path, the orphaned behavioral monitor, the RAG gate, the impossible CI docker build contexts, and the compose secrets.
- No runtime observation was available: nothing was executed, no container was started, no trace or log was inspected. Every claim is static evidence from code, config or docs.
- Twelve decisions in `decision-map.md` are **open**, and five assumption-register entries could change the sequencing. The recommendations are argued, not authoritative.
