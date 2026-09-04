# evalguard.contamination — Training Data Contamination Auditor

The `evalguard.contamination` module detects benchmark contamination using four complementary signals:

---

## 1. Lexical Contamination
- **Configurable N-Gram Sliding Windows**: Analyzes token overlap across 3-gram through 8-gram orders.
- **Exact and Fuzzy Matching**: Employs Levenshtein edit distance (≤ 2) to catch slightly obfuscated verbatim copies.
- **Metrics**: Computes Jaccard similarity, containment score, and longest contiguous token sequence.

---

## 2. Semantic Contamination
- **Offline Embedding Backends**: Default `sentence-transformers` backend (`all-MiniLM-L6-v2`) runs completely offline.
- **Configurable Thresholds**: Flags tasks where cosine similarity exceeds the configurable threshold (default `0.85`).

---

## 3. Disclosure Timeline Analysis
- Compares the agent's pre-training knowledge cutoff date against the official public disclosure date of the benchmark.
- Flags any agent trained after benchmark disclosure as `POTENTIALLY EXPOSED`.

---

## 4. Differential Cohort Analysis
- Evaluates task pass rates across a population of agents.
- Flags tasks where an individual agent's performance is an extreme statistical outlier (Z-score > 2.5) relative to the rest of the field, indicating task-specific memorization.
