# Lot Zero — Social & Blog Publication Pack

---

## 1. Technical Deep Dive Blog Post (Dev.to / Medium / Substack)

### Title:
**Why We Built an Event-Sourced Kernel for Gemini 3.5: Deterministic Food Safety Recalls on Google Cloud Run**

### Summary / Subtitle:
How we combined Gemini 3.5 Flash on Google Vertex AI, an append-only event store on GCS FUSE, strict Separation of Duties, and SHA-256 hash chains to build a regulated recall workspace.

> *Disclosure: This project was created for the purposes of entering the All Things Agentic Hackathon.*

---

### Article Body:

When software operates in regulated environments like food manufacturing or pharmaceuticals, "probabilistic correctness" is unacceptable. Federal regulations like **FDA 21 CFR § 7.49** dictate stringent requirements for product quarantine, consignee notification, dual-signature hold releases, and tamper-evident auditability.

Most modern AI solutions attempt to solve this by wrapping an LLM in a prompt that asks it to "be accurate." But in high-concurrency, high-liability domains, LLMs should propose—**deterministic kernels must decide**.

In this post, we explore the architecture of **Lot Zero**, an open-source recall incident workspace built with **Gemini 3.5 Flash on Vertex AI**, **Google Cloud Run**, and an append-only event store.

---

### Pillar 1: Grounded Extraction with Character-Offset Citations
Safety notices from analytical testing laboratories arrive as unstructured text reports. Using the official `google-genai` SDK on **Google Vertex AI** (`location="global"`) with Application Default Credentials (ADC), Lot Zero invokes `gemini-3.5-flash` to extract:
1. Contaminated raw ingredient lot numbers (`ING-4417`)
2. Pathogen classifications (`Salmonella enterica`)
3. Exact character-offset citation spans tied directly to the source report's SHA-256 hash.

```python
from google import genai
import os

client = genai.Client(
    vertexai=True,
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "project-b2c3348e-d718-4255-be2"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "global")
)

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=extraction_prompt
)
```

The AI extracts structured signals, but the domain kernel verifies that every claim is bounded by verifiable document spans and isolates finished products (`FP-100-L240814-A` and `B`) while keeping clean controls (`FP-100-ADJ`) unblocked.

---

### Pillar 2: Strict Separation of Duties (No Self-Approvals)
In the chaos of an active incident, organizational hierarchy is often breached. In Lot Zero, the domain authority kernel enforces strict role separation:
- A **Recall Coordinator** can propose scope and simulate signals.
- A **QA Lead** must independently sign off on firm quarantines.
- If the requester attempts to approve their own scope, the kernel immediately rejects the command with **HTTP 403 Forbidden** (`requester and approver must be different people`).

---

### Pillar 3: Single-Writer GCS FUSE Persistence on Google Cloud Run
To preserve event history without heavy database operational overhead, Lot Zero mounts a dedicated Google Cloud Storage bucket (`gs://lot-zero-events-...`) via Cloud Run volume mounts (gcsfuse) directly to `/app/data/lot_zero.db`.

Because GCS FUSE does not support POSIX file locking, we deploy Cloud Run with `--max-instances=1` by design. All state transitions are modeled as pure reducers over immutable domain events with optimistic concurrency (`expected_version`).

---

### Pillar 4: Tamper-Evident SHA-256 Audit Chains
Regulatory audits often happen months after an incident. Rather than trusting mutable database rows, Lot Zero exports a cryptographically chained JSON bundle where each event's hash includes the previous event's digest:

$$H_i = \text{SHA-256}(H_{i-1} \parallel \text{EventPayload}_i)$$

If any bad actor reorders events, edits timestamps, or omits a refusal, the top-level root digest immediately breaks, providing instant proof of tampering.

---

### Conclusion & Links
- **Live Cloud Run Demo**: [https://lot-zero-1051797806634.us-central1.run.app](https://lot-zero-1051797806634.us-central1.run.app)
- **GitHub Repository**: [https://github.com/ryuzaki1709/lot-zero](https://github.com/ryuzaki1709/lot-zero)
- **119 Tests Passing**: Contracts, optimistic concurrency, and audit tamper tests verified 100%.

---

## 2. X (Twitter) Launch Thread

**Post 1/5**:
🚨 Recalls in regulated manufacturing can't tolerate AI hallucinations or mutable records.

Introducing **Lot Zero** — an evidence-backed food safety incident workspace built with @GoogleCloud & #Gemini3.5 on Vertex AI.

Live demo: https://lot-zero-1051797806634.us-central1.run.app
GitHub: https://github.com/ryuzaki1709/lot-zero
🧵👇 #GoogleCloud #VertexAI #AgenticAI #BuildWithAI

**Post 2/5**:
1️⃣ Grounded Extraction:
Raw Salmonella lab notices are ingested via Gemini 3.5 Flash on Vertex AI (global endpoint, ADC). Citations are bound to character-level offsets and anchored to the source lab document's SHA-256 digest. No hallucinated inventory counts.

**Post 3/5**:
2️⃣ Server-Enforced Separation of Duties:
Requester ≠ Approver. If a Recall Coordinator attempts to sign off on their own quarantine, the domain kernel enforces an immediate HTTP 403 refusal. 21 CFR § 7.49 compliance is built into the architecture.

**Post 4/5**:
3️⃣ Tamper-Evident SHA-256 Audit Chains:
Every event in the incident lifecycle is cryptographically chained to its predecessor. Any event reordering, timestamp modification, or omission breaks the root digest.

**Post 5/5**:
4️⃣ Cloud Native Architecture:
- Google Cloud Run (FastAPI + React SPA)
- Cloud Storage (GCS FUSE persistent event store)
- Secret Manager (HMAC-signed SSE streams)
- 119/119 tests passing! 🚀

Check out the full walkthrough: https://lot-zero-1051797806634.us-central1.run.app

---

## 3. LinkedIn Post (Engineering & AI Safety Audience)

**Headline**: Why Regulated AI Applications Need Event-Sourced Deterministic Kernels: Announcing Lot Zero

In high-stakes industries like food manufacturing and life sciences, standard LLM wrappers fall short because probabilistic answers cannot meet statutory compliance standards (such as FDA 21 CFR § 7.49).

To solve this, we built **Lot Zero**: an industrial-grade recall incident platform engineered around a simple thesis:
👉 *Generative AI should propose, but deterministic event-sourced kernels must decide.*

Key Architecture Highlights:
🔹 **Google Vertex AI (`gemini-3.5-flash`)**: Extracts contaminated raw lot signals with bounding citation spans and SHA-256 document anchors.
🔹 **Separation of Duties Authority Kernel**: Server-enforced anti-collision gates preventing self-approvals (HTTP 403 on conflict).
🔹 **Google Cloud Run + GCS FUSE Persistence**: Persistent SQLite append-only event store deployed with single-writer concurrency safety.
🔹 **Cryptographically Chained Audit Trail**: Self-verifying SHA-256 event streams that expose any record tampering, omission, or reordering.

Explore the live deployed platform on Google Cloud:
🔗 Live Service: https://lot-zero-1051797806634.us-central1.run.app
📁 Source Code: https://github.com/ryuzaki1709/lot-zero

*(Note: Created for the purposes of entering the All Things Agentic Hackathon)*

#GoogleCloud #VertexAI #Gemini #SoftwareEngineering #EventSourcing #FastAPI #React #CyberSecurity
