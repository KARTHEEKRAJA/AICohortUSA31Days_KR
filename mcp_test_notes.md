# MCP Test Notes — Day 23 (coverage-tools ⇄ Claude Desktop)

**Stack:** MCP Python SDK 1.28.1 (FastMCP) · stdio transport · server
`coverage-tools` exposing `check_coverage` + `get_claim_status` · internals:
Day 10 `vector_lookup()` (with Day 9's metadata filter) + Day 4 plans table +
Day 13's validated decision logic · client: Claude Desktop (Microsoft Store
build) on Windows.

## Manifest (per MCP spec — name · description · schema)
- SERVER: `coverage-tools` — instructions describe scope + "mock/demo data"
- TOOL `check_coverage(plan_id: str, procedure: str)` — schema auto-derived
  from type hints: required string properties, titled object
- TOOL `get_claim_status(claim_id: str)` — same pattern
- Verified with a list_tools probe before registration (JSON Schema captured)

## Registration — the path saga (the day's first lesson)
`%APPDATA%\Claude\claude_desktop_config.json` was written first — and turned
out to be an EMPTY DECOY: the Microsoft Store build keeps its real home at
`%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\`. Diagnosis:
the decoy folder contained only our own file (no logs, no app data). The real
folder already held a config with app preferences → MERGED (never clobbered)
an `mcpServers` block into it. Second lesson inside the first: closing the
window does NOT restart Desktop — tray-quit (or Stop-Process) is required for
config reload. After the true restart: `coverage-tools` appeared under
+ → Connectors, toggled on.

## Tool-call confirmations (4/4)
1. **"Is an MRI covered under plan P101?"** → "Loaded tools, used
   coverage-tools integration" → covered ✓, 10% coinsurance, $2,000/$4,000
   deductibles, $6,500/$13,000 OOP caps — audited vs knowledge_base.jsonl:
   every figure present in chunk_0000 (Gold SBC). Fully grounded; the
   frontier client mined the SAME tool output far deeper than our local 3Bs
   ever did. **MCP lets you upgrade the brain without touching the plumbing.**
2. **"Is an MRI covered under plan P103?"** → decision correct (not covered,
   Bronze) — but the client FLAGGED that the accompanying policy text came
   from P101's document. **The client audited the tool and caught a real
   bug:** `vector_lookup` ran unfiltered, so Gold's SBC (strongest "MRI"
   match) hitchhiked onto every plan's answers.
3. **"What's the status of claim C1001?"** → get_claim_status debut:
   Pending · M1001 · X-ray · $250.00 ✓
4. **"Is claim C-9999 approved?"** → honest not-found — and the client
   narrated our shim's behavior ("the system normalized your input to
   C9999"), reading the tool's normalization from its output. ✓

## The fix (finding #2 → resolved)
Day 9's `where=` metadata filter — built 14 days ago, unused since — now
scopes context to `{"plan_type": {"$in": [<plan's type>, "all"]}}` with the
plan name in the query. Re-test in a FRESH chat: P101-document complaint
gone; the client's only remaining note was honest tension inside the mock
corpus itself (general imaging coinsurance text vs MRI carve-out).

## Findings
1. **The config decoy:** Store-build Desktop reads config from the package
   sandbox, not %APPDATA%. An empty-looking install ≠ no install.
2. **Window-close ≠ restart:** config loads once per process; tray-quit or
   kill to reload. (Cost us one full round of confusion.)
3. **The client audited my tool:** Claude Desktop cross-checked decision vs
   returned context and refused to paper over the mismatch — surfacing a
   grounding bug my own review missed. Frontier clients are a QA layer.
4. **Clients cache — fresh chats for fixes:** the first post-fix P103 test
   "verified previous assessment" from conversation memory without calling
   the server. Contaminated chats cannot test fixes (Day-20's lesson, client
   edition).
5. **Same plumbing, better brain:** identical tool JSON that 3B models
   skimmed for one number became benefits-counselor prose under a frontier
   model. The protocol decouples tool quality from client capability.

## Security note (per mission warning)
No API keys anywhere; the Desktop config (paths only) is NOT committed —
repo ships mcp_server.py + this file only.