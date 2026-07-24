# Vector Database Notes — Day 8

Comparing the two databases stood up today: **Chroma** (local, persistent client)
and **Pinecone** (cloud, serverless free tier). Both hold the same kind of data:
384-dim embeddings from all-MiniLM-L6-v2 with chunk metadata.

## Comparison Table

| Criteria | Chroma (local) | Pinecone (cloud) |
|---|---|---|
| **Local vs cloud** | Runs fully on my machine; data in a local `chroma_db/` folder. No network needed, works offline. | Fully managed cloud service; data lives in Pinecone's infrastructure (AWS us-east-1 serverless). Requires internet + API key. |
| **Free-tier limits** | No limits — open source, free forever. Bounded only by my disk/RAM. | Starter tier: no credit card, but capped (limited # of serverless indexes, storage, and read/write units per month). Fine for learning; production needs paid tier. |
| **Latency** | Sub-millisecond to low-ms — everything is in-process, no network hop. | Network round-trip per query (tens of ms from my machine). Low within same cloud region, but always slower than in-process for small datasets. |
| **Ease of setup** | One pip install + 3 lines of Python. Collection created in seconds. | Account signup, dashboard index creation (dimension must match the model — 384), API-key management, and a package rename gotcha (`pinecone-client` is deprecated → install `pinecone`). More moving parts. |
| **Access control (enterprise, per-member / per-plan)** | None built in — Chroma has no auth layer. Access control must be enforced entirely in my application code (e.g., filter by `plan_type` metadata before returning results). Risky at enterprise scale; a bug leaks another member's data. | API keys + namespaces + metadata filtering. Per-plan data can be isolated in separate namespaces or enforced via server-side metadata filters; enterprise tiers add RBAC, SSO, and audit logs. Better fit for PHI-adjacent workloads where isolation must be provable. |

## Decision: Chroma

**Going forward in this program, I'm using Chroma.** It is fully free with no usage caps, runs locally with zero network latency, and needs no API keys — which means no secrets to manage and nothing to leak into the repo. Its persistent client survives restarts, which is all the durability a 13-chunk learning project needs, and staying local keeps the whole pipeline (Ollama LLM,sentence-transformers embeddings, Chroma retrieval) consistent with the program's local-first architecture. Pinecone remains the right answer for a real enterprise deployment — its namespaces, server-side filtering, and audit capabilities matter for healthcare data isolation — but for the next 23 days, Chroma's simplicity wins: fewer moving parts between me and the actual learning.

**For a real enterprise deployment: Pinecone (or equivalent managed service).**
The deciding factor is not speed or cost — it is access control and operational responsibility. Healthcare coverage data demands provable member/plan isolation, audit trails, and someone accountable for uptime and backups. A managed service provides those; a local library makes them my problem.

## Notes from today's setup

- Pinecone index dimension must exactly match the embedding model (384 for
  all-MiniLM-L6-v2) — a mismatch fails at insert time, not creation time.
- `pinecone-client` package is deprecated; the SDK is now `pinecone`.
- Chroma data folder and the Pinecone API key are gitignored — no secrets in the repo.