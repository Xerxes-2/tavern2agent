# tavern2agent

[中文](README_ZH.md)

Compile SillyTavern character cards into pi-native interactive narrative runtimes.

v2 no longer treats a character card as a bundle of prompts, lorebooks, and status panels. It first extracts the card's semantics, then generates a domain-event-driven runtime:

```txt
SillyTavern card
  → Card Semantic IR
  → Runtime Plan
  → Event Packs + State Schema + Reducers + Tools
  → Prompt Orchestrator
  → pi project
```

The core principle: **prompts describe the world; domain events change it.**

## Scope

Supported inputs:

- ST v1/v2/v3 cards in PNG, WEBP, JPEG, or JSON format
- Setting-only cards
- Lorebook/MVU cards
- System-heavy cards with dice, combat, affinity, economy, quests, time, and similar mechanics
- Hidden-information, multi-NPC, and multi-agent scenarios

The compiler removes HTML status panels, frontend UI, image-generation prompts, ST macro runtime patches, chain-of-thought tags, and JSON Patch output formats by default. The underlying fields, rules, trigger conditions, and prompt-composition ideas can still be migrated.

## Installation

Using [`npx skills`](https://github.com/vercel-labs/skills) (recommended):

```bash
npx skills add Xerxes-2/tavern2agent
```

Or clone the repository:

```bash
git clone --depth 1 https://github.com/Xerxes-2/tavern2agent \
  ~/.pi/agent/skills/tavern2agent
```

To update:

```bash
npx skills update            # Installed with npx skills
cd ~/.pi/agent/skills/tavern2agent && git pull   # Installed with git clone
```

## Usage

```bash
mkdir my-card && cd my-card
cp ~/Downloads/card.png .
pi
# Tell the agent: Convert this character card for me.
```

The agent unpacks the card, audits its lorebooks and scripts, generates `world-data/card-ir.json`, proposes a Runtime Plan, selects event packs, sources of truth, and subagent roles, then generates and validates a pi project. For complex cards, it presents the Runtime Plan, state schema, event catalog, tool/API list, and subagent boundaries before writing code.

## Output

Setting-only cards with no mutable world or secrecy boundaries are not converted—the benefit does not justify the cost, so using the original card is recommended.

Cards with mutable concepts produce an evented runtime:

```txt
project/
├── .pi/settings.json
├── prompts/preset.json
├── prompts/gm-*.md
├── world-data/card-ir.json
├── world-data/runtime-plan.json
├── world-data/*.json
├── engine/events.ts
├── engine/reducers.ts
├── engine/state.ts
├── tools/registry.ts
├── extension.ts
├── skills/start-game/SKILL.md
└── start.sh
```

Additional files may include `engine/migrations.ts`, `engine/codeact.ts`, `engine/codeact-sandbox.d.ts`, `extensions/subagents/*`, `.pi/agents/*`, event-pack-specific data, and tests.

`runtime/`, `sessions/`, `.pi/agent/`, and `.pi/npm/` are not published.

## Approach

This table is a reader-friendly overview. See `references/decision-tree.md` for the authoritative decision process.

| Card characteristics | v2 approach |
|---|---|
| No mutable world or secrecy boundaries | Do not convert; use the original card |
| A few mutable concepts | Evented light: typed domain tools + reducer |
| Interdependent fields, dice, combat, economy, or time compression | Evented standard: event packs + reducer + typed tools / CodeAct API |
| Hidden information, secret viewpoints, or multiple factions | Add secret / faction / offscreen packs and project subagents |
| Real-world settings, open-source projects, APIs, or live information | External research tools + local canonical data |

CodeAct is only an execution environment for domain APIs. Whether the runtime uses typed tools or CodeAct, every state change must become a domain event and pass through a reducer.

Web search, web fetching, and code search can replace manually maintained knowledge bases, but only as read-only fact sources. Canonical card facts remain in local `world-data` and lookup modules. Subagents produce viewpoint reactions, offscreen candidates, or audit opinions; they never write state directly.

## Documentation

```txt
SKILL.md                         Agent entry workflow
references/evented-runtime.md    v2 constitution
references/card-ir.md            Card Semantic IR
references/event-packs.md        Domain event packs
references/data-layer.md         Local lookup and external research boundaries
references/multi-agent-architecture.md Subagent design
references/two-pass-rendering.md Settlement/rendering split and compaction
references/                      Migration details
docs/developing-cards.md         Post-migration maintenance
docs/tooling.md                  Optional tools
scripts/                         Card unpacking and audit scripts
```

## Production Example

This skill's methodology is continuously validated and refined in [fate-sandbox](https://github.com/lolo-s-Cosmos/fate-sandbox), a Type-Moon universe sandbox spanning 13 timelines, including FSN Fuyuki, strange Fake, Tsukihime, and The Garden of Sinners. Its settlement/rendering split, engine ledger, deterministic compaction, and cache-friendly rendering history all grew out of long-running production use there. To see a complete evented standard project with multiple subagents and two-pass processing, read its source and `docs/adr/`.

## Philosophy

Do not reproduce ST runtime patches. Understand the game the card author intended, then rebuild it with pi-native capabilities: facts are queryable, rules are computable, events are auditable, state is migratable, secrets do not leak across layers, and the narrative never breaks the fourth wall.
