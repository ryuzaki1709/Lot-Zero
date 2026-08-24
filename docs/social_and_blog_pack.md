# Lot Zero — Social & Blog Publication Pack

---

## 1. Technical Deep Dive Blog Post (Dev.to / Medium / Substack)

### Title:
**Why We Built a Deterministic Domain Kernel for Gemini 3.5: Evidence-Grounded Food Safety Recalls on Google Cloud**

### Summary / Subtitle:
How we combined Gemini 3.5 Flash on Google Vertex AI, an append-oriented event store, strict Separation of Duties, and SHA-256 hash chains to build a regulated recall workspace.

> *Disclosure: This project was created for the purposes of entering the All Things Agentic Hackathon.*

---

### Article Body:

When software operates in regulated environments like food manufacturing or pharmaceuticals, "probabilistic correctness" is insufficient. Recall operations dictate stringent requirements for product quarantine, consignee notification, dual-signature hold releases, and tamper-evident auditability.

Most modern AI solutions attempt to solve this by wrapping an LLM in a prompt that asks it to "be accurate." But in high-concurrency, high-liability domains, LLMs should propose—**deterministic kernels must decide**.

In this post, we explore the architecture of **Lot Zero**, an open-source recall incident workspace built with **Gemini 3.5 Flash on Vertex AI**, **Google Cloud Run**, and an append-oriented event store.

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
    project=os.getenv("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID"),
    location=os.getenv("GOOGLE_CLOUD_LOCATION", "global")
)

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=extraction_prompt
)
```

The AI extracts structured signals, but the domain kernel verifies that every claim is bounded by verifiable document spans and isolates finished products (`FP-100-AFF`, 200 units) while keeping clean controls (`FP-100-ADJ`) unblocked (0 false holds).

---

### Pillar 2: Strict Separation of Duties (No Self-Approvals)
In the chaos of an active incident, organizational hierarchy is often breached. In Lot Zero, the domain authority kernel enforces role separation across 5 Evaluation Personas (4 Operational Personas + Evaluation Administrator):
- A **Recall Coordinator** can propose scope and simulate signals.
- A **QA Lead** must independently sign off on firm quarantines.
- If the requester attempts to approve their own scope, the kernel rejects the command with **HTTP 403 Forbidden** (`requester and approver must be different people`).

---

### Pillar 3: Single-Instance Container Deployment on Google Cloud Run
For public hackathon evaluation, Lot Zero packages FastAPI and the React SPA into a single container running with `--max-instances=1`. All state transitions are modeled as pure reducers over domain events with optimistic concurrency (`case_version`).

---

### Pillar 4: Tamper-Evident SHA-256 Audit Chains
Regulatory audits often happen months after an incident. Rather than trusting mutable database rows, Lot Zero exports a cryptographically chained JSON bundle where each event's hash includes the previous event's digest:

$$H_i = \text{SHA-256}(H_{i-1} \parallel \text{EventPayload}_i)$$

If any bad actor reorders events, edits timestamps, or removes records after export, the top-level root digest breaks, providing immediate proof of tampering against the exported root digest.

---

### Conclusion & Links
- **Live Demo**: `[LIVE_DEMO_URL_PLACEHOLDER]`
- **GitHub Repository**: [https://github.com/ryuzaki1709/lot-zero](https://github.com/ryuzaki1709/lot-zero)
- **164 Tests Passing**: Contracts, optimistic concurrency, and audit tamper tests verified.

---

## 2. X (Twitter) Launch Thread

**Post 1/5**:
🚨 Recalls in regulated manufacturing can't tolerate AI hallucinations or mutable records.

Introducing **Lot Zero** — an evidence-backed food safety incident workspace built with @GoogleCloud & #Gemini3.5 on Vertex AI.

Demo: `[LIVE_DEMO_URL_PLACEHOLDER]`
GitHub: https://github.com/ryuzaki1709/lot-zero
🧵👇 #GoogleCloud #VertexAI #AgenticAI #BuildWithAI

**Post 2/5**:
1️⃣ Grounded Extraction:
Raw Salmonella lab notices are ingested via Gemini 3.5 Flash on Vertex AI (global endpoint, ADC). Citations are bound to character-level offsets and anchored to the source lab document's SHA-256 digest. No hallucinated inventory counts.

**Post 3/5**:
2️⃣ Server-Enforced Separation of Duties:
Requester ≠ Approver. If a Recall Coordinator attempts to sign off on their own quarantine, the domain kernel enforces an immediate HTTP 403 refusal across 5 evaluation personas.

**Post 4/5**:
3️⃣ Tamper-Evident SHA-256 Audit Chains:
Every event in the incident lifecycle is cryptographically chained to its predecessor. Any event reordering, timestamp modification, or omission breaks the root digest.

**Post 5/5**:
4️⃣ Cloud Native Architecture:
- Google Cloud Run (FastAPI + React SPA)
- Environment-configured secrets (Secret Manager recommended for production)
- 164 backend tests + 25 frontend tests passing! 🚀

Check out the full repository: https://github.com/ryuzaki1709/lot-zero

---

## 3. LinkedIn Post (Engineering & AI Safety Audience)

**Headline**: Why Regulated AI Applications Need Deterministic Domain Kernels: Announcing Lot Zero

In high-stakes industries like food manufacturing and life sciences, standard LLM wrappers fall short because probabilistic answers cannot meet strict audit standards.

To solve this, we built **Lot Zero**: an evidence-grounded recall incident platform engineered around a simple thesis:
👉 *Generative AI should propose, but deterministic event-sourced kernels must decide.*

Key Architecture Highlights:
🔹 **Google Vertex AI (`gemini-3.5-flash`)**: Extracts contaminated raw lot signals with bounding citation spans and SHA-256 document anchors when configured.
🔹 **Separation of Duties Authority Kernel**: Server-enforced anti-collision gates preventing self-approvals (HTTP 403 on conflict).
🔹 **Google Cloud Run Deployment**: Single-instance container deployment with real-time SSE updates.
🔹 **Cryptographically Chained Audit Trail**: Self-verifying SHA-256 event streams that detect post-export tampering, omission, or reordering.

Explore the source code on GitHub:
📁 Source Code: https://github.com/ryuzaki1709/lot-zero
🔗 Live Demo: `[LIVE_DEMO_URL_PLACEHOLDER]`

*(Note: Created for the purposes of entering the All Things Agentic Hackathon)*

#GoogleCloud #VertexAI #Gemini #SoftwareEngineering #EventSourcing #FastAPI #React #CyberSecurity
