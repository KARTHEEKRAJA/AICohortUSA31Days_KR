from sentence_transformers import SentenceTransformer

# Load once at module level — loading per-call would be very slow
model = SentenceTransformer("all-MiniLM-L6-v2")   # downloads ~90MB on first run

def embed(text: str) -> list[float]:
    """Convert a string into a numeric vector capturing its meaning."""
    vector = model.encode(text)
    return vector.tolist()

# --- Test it ---
v = embed("What is the deductible on the Gold PPO plan?")
print("Vector length:", len(v))
print("First 5 values:", v[:5])

import json
import numpy as np

# --- 1. Load the knowledge base ---
with open("knowledge_base.jsonl", encoding="utf-8") as f:
    records = [json.loads(line) for line in f]
print(f"Loaded {len(records)} chunks")

# --- 2. Embed all chunks in one batch ---
texts = [r["text"] for r in records]
vectors = model.encode(texts, show_progress_bar=True)   # shape: (n_chunks, 384)
print("Embeddings shape:", vectors.shape)

# --- 3a. Attach embedding field to each record ---
for record, vec in zip(records, vectors):
    record["embedding"] = vec.tolist()

with open("knowledge_base_embedded.jsonl", "w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("Wrote knowledge_base_embedded.jsonl")

# --- 3b. Also save the required embeddings.npy (parallel array) ---
np.save("embeddings.npy", vectors)
print("Wrote embeddings.npy")

# --- 4. Verify integrity ---
loaded = np.load("embeddings.npy")
assert loaded.shape == (len(records), 384), "shape mismatch!"
assert np.allclose(loaded[0], records[0]["embedding"]), "index 0 mismatch!"
print(f"Verified: {loaded.shape[0]} embeddings x {loaded.shape[1]} dims, index-aligned")

import matplotlib
matplotlib.use("Agg")          # render to file (no GUI needed)
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA

# --- 1. Reduce 384 dims -> 2 dims ---
pca = PCA(n_components=2)
points_2d = pca.fit_transform(vectors)          # shape: (13, 2)
print("Reduced shape:", points_2d.shape)
print("Variance explained:", pca.explained_variance_ratio_.sum().round(3))

# --- 2. Scatter plot, color-coded by section ---
sections = [r["section"] for r in records]
colors = {"coverage": "#1E6FD9", "exclusions": "#E63329",
          "claims": "#2E9E5B", "enrollment": "#F5A623"}

plt.figure(figsize=(10, 7))
for section in colors:
    xs = [p[0] for p, s in zip(points_2d, sections) if s == section]
    ys = [p[1] for p, s in zip(points_2d, sections) if s == section]
    plt.scatter(xs, ys, c=colors[section], label=f"{section} ({len(xs)})", s=90)

plt.legend()
plt.title("Knowledge Base Embeddings — PCA 2D (colored by section)")
plt.xlabel("PC1")
plt.ylabel("PC2")
plt.grid(alpha=0.3)
plt.tight_layout()
plt.savefig("embeddings_pca.png", dpi=150)
print("Saved embeddings_pca.png")

from sklearn.metrics.pairwise import cosine_similarity

# --- 1. Save with the REQUIRED filename ---
plt.savefig("embeddings_2d.png", dpi=150)   # re-save from the same figure if still open
# If the figure was closed, just rename the file instead:
# import os; os.replace("embeddings_pca.png", "embeddings_2d.png")
print("Saved embeddings_2d.png")

# --- 2. Quantified sanity check: within-section vs cross-section similarity ---
sims = cosine_similarity(vectors)           # 13x13 matrix, 1.0 = identical meaning

same, diff = [], []
for i in range(len(records)):
    for j in range(i + 1, len(records)):
        pair = sims[i][j]
        if records[i]["section"] == records[j]["section"]:
            same.append(pair)
        else:
            diff.append(pair)

print(f"Avg similarity SAME section:  {np.mean(same):.3f}")
print(f"Avg similarity CROSS section: {np.mean(diff):.3f}")

# --- 3. Spot-check: nearest neighbor of each claims/exclusions chunk ---
for i, r in enumerate(records):
    if r["section"] in ("claims", "exclusions"):
        nn = int(np.argsort(sims[i])[-2])   # -1 is itself
        print(f"\n[{r['section']}] {r['text'][:60]}...")
        print(f"  nearest -> [{records[nn]['section']}] {records[nn]['text'][:60]}...")