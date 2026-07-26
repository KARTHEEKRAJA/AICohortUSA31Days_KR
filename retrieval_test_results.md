# Retrieval Engine Test Results — Day 10

**Engine:** keyword classifier → sql_lookup (templated, parameterized SQL over
coverage.db) + vector_lookup (Chroma, all-MiniLM-L6-v2, optional metadata
filter) → retrieve() orchestrator with fallback and de-duplication.
**Scoring:** good = right source, right answer · partial = right direction,
imperfect result · poor = wrong/no useful result.

## Score Table

| # | Question | Classification | Retrieved context (summary) | Score |
|---|---|---|---|---|
| T01 | what's my copay | structured | SQL: all 3 plans with copay_pct (no plan named → generic template) | good |
| T02 | is maternity care covered on the Bronze plan | unstructured | HMO-filtered chunks; Bronze plan record #1 (d=1.207) — maternity absent from KB, distances honest-weak | partial |
| T03 | status of claim C-2031 | unstructured | No SQL (ID format unparsed; claim doesn't exist) → vector fallback: claims-process guide (d=1.157) | partial |
| T04 | monthly premium for the Gold plan | structured | SQL: Gold PPO row — $500/month | good |
| T05 | which plans are under $400 a month | structured | SQL: Bronze $150, Silver $300 (sorted) | good |
| T06 | claim status for member M1001 | structured | SQL: C1001 Pending, C1002 Approved | good |
| T07 | how do I appeal a denied claim | both* | Appeals chunk d=0.537 (strong); SQL over-called but empty → dropped | good |
| T08 | what services are not covered | unstructured | Exclusions chunk ranked #2 (d=1.18) behind a glossary chunk (d=1.076) | partial |
| T09 | how do I enroll in a health plan | unstructured | Picking-a-plan d=0.569 + enrollment form d=1.014 | good |
| T10 | Silver deductible + how to file a claim (mixed) | both | SQL: Silver deductible $1500 ✓; vector missed claims content (see finding 4) | partial |

**Result: 6 good · 4 partial · 0 poor.**

## Findings

1. **Distance threshold discovered (~1.0).** When the answer exists, top
   distances are 0.53–0.57 (T07, T09). When it doesn't, everything sits at
   1.07+ (T02, T03). A ~1.0 cutoff would let the engine say "no information"
   instead of passing weak context downstream.
2. **The engine is resilient to classifier mistakes.** T07's "both" over-call
   (keyword "denied") cost nothing — empty SQL results drop out of the merge.
   Mis-routes degrade gracefully rather than break.
3. **T03 exposes entity-extraction gaps.** `C-2031` doesn't match my member-ID
   regex, and no claim-ID template exists. Vector fallback returned reasonable
   generic content, but production should answer "claim C-2031 not found."
4. **T10: metadata filtering over-constrained.** "Silver" triggered the
   plan_type=HMO filter, which excluded claims-process chunks (tagged
   plan_type="all"). The filter that fixed Day 9's wrong-plan miss *removed*
   the right answer here. Fix: `where={"plan_type": {"$in": ["HMO", "all"]}}` —
   include plan-agnostic content alongside plan-specific.
5. **T08 traces retrieval quality back to chunking.** The true exclusions text
   lives in chunk_0001 — the chunk my Day 7 PCA plot flagged as mislabeled
   (mostly coinsurance content, exclusions trailing). Diluted chunks rank
   poorly. Chunk quality (Day 6) → embedding quality (Day 7) → retrieval
   quality (Day 10): one pipeline, compounding.

**One-line takeaway:** the hybrid engine routes correctly and degrades
gracefully; its remaining misses are diagnosed, named, and fixable — thresholds,
`$in` filters, and richer entity extraction.

\* classifier over-call, self-corrected by the orchestrator.