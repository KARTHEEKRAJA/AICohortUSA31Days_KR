# Vector Query Test — Day 9

**Query:** "Is physical therapy covered under the Silver plan?"
**Method:** all-MiniLM-L6-v2 embedding → `collection.query(n_results=5)` against
`coverage_kb` (13 chunks, cosine distance — lower = more similar).

## Results

| Rank | ID | Distance | Section | Plan | Source | Content (summary) |
|---|---|---|---|---|---|---|
| 1 | chunk_0000 | 1.090 | coverage | PPO | benefits.txt | Gold PPO SBC header: deductibles, copays, coverage period |
| 2 | chunk_0001 | 1.124 | exclusions | all | benefits.txt | Imaging/surgery coinsurance + exclusions list |
| 3 | chunk_0011 | 1.131 | coverage | HMO | coverage.db | **Silver HMO plan record** — premium, deductible, copay |
| 4 | chunk_0009 | 1.172 | coverage | all | webpage_faq.txt | How to pick a health plan |
| 5 | chunk_0007 | 1.228 | coverage | all | webpage_faq.txt | Glossary: covered services, insurer pays the rest |

## Are they relevant?

Partially. All five are coverage-section content, so the topic matched. But
"physical therapy" appears nowhere in the knowledge base, and the distances show
it: 1.09–1.23 is a weak, tightly-bunched band. The system returned the
least-distant neighbors it had rather than a genuinely strong match — which is
the correct behavior when the answer isn't in the corpus.

## Do they reflect Silver-plan-specific coverage?

**No — and this is the key finding.** The #1 result is the *Gold PPO* chunk, not
Silver. It ranked highest because it is the densest block of coverage vocabulary
(deductible, coinsurance, copay) in the corpus. Pure vector search treats
"Silver" as just another word contributing to similarity — it cannot enforce
"Silver" as a *constraint*. The only truly Silver-specific chunk (chunk_0011,
the DB plan record) ranked #3.

## Retrieval misses & lessons

1. **Wrong plan ranked first.** Semantic similarity ≠ constraint satisfaction.
   Fix: metadata pre-filtering (`plan_type = "HMO"`) before vector search —
   exactly what the Day 6 metadata schema was designed for, and what Day 10's
   hybrid retrieval implements.
2. **No answer exists, but results still return.** Without a distance threshold,
   a downstream LLM would receive weak context and might answer confidently
   anyway. A production system should detect the ~1.1+ distance band and respond
   "no information on physical therapy" instead.
3. **An `exclusions` chunk ranked #2** for a coverage question — vocabulary
   overlap between covered and excluded services. Metadata filtering by section
   would separate these when it matters.

**One-line takeaway:** raw vector search finds *topics*, not *answers* —
metadata filters and distance thresholds turn it into retrieval you can trust.

## Filtered vs Unfiltered (Step 6)

**Filter `{"plan_type": "Silver"}` (mission's example):** 0 results — my schema
stores plan *types* (HMO/PPO/all), not plan names. A filter is only as good as
the metadata vocabulary it queries; mismatched values fail silently to empty.

**Filter `{"plan_type": "HMO"}` (correct for my schema):** results scoped to
HMO chunks only. The Silver HMO record (chunk_0011) now ranks #1 — the Gold PPO
chunk that topped the unfiltered query is excluded by construction, not by luck.

| Query | #1 result | Silver-specific? |
|---|---|---|
| Unfiltered | chunk_0000 — Gold PPO | ✗ wrong plan |
| where plan_type=HMO | chunk_0011 — Silver HMO | ✓ |

**Confirmed:** metadata filtering scopes retrieval to one plan family and fixes
the wrong-plan-first miss. Semantic search finds the topic; metadata enforces
the constraint. Both are needed.