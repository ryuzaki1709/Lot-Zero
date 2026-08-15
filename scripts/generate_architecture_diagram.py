"""Generate clean, publication-quality architecture diagram (SVG) for Lot Zero."""

import os

SVG_CONTENT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 720" width="1200" height="720" style="background:#0f172a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
  <defs>
    <linearGradient id="gradClient" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e293b" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
    <linearGradient id="gradCompute" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#1e293b" />
      <stop offset="100%" stop-color="#0f172a" />
    </linearGradient>
    <linearGradient id="gradBox" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#334155" />
      <stop offset="100%" stop-color="#1e293b" />
    </linearGradient>
    <filter id="shadow" x="-5%" y="-5%" width="110%" height="110%">
      <feDropShadow dx="0" dy="4" stdDeviation="6" flood-color="#000000" flood-opacity="0.4"/>
    </filter>
    <marker id="arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#38bdf8" />
    </marker>
    <marker id="arrowGreen" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#00dc82" />
    </marker>
    <marker id="arrowPurple" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#a855f7" />
    </marker>
  </defs>

  <!-- Title Header -->
  <text x="40" y="45" fill="#f8fafc" font-size="22" font-weight="700" letter-spacing="-0.5">Lot Zero — System Architecture</text>
  <text x="40" y="68" fill="#94a3b8" font-size="13">Deterministic Regulated Recall Workspace · Google Cloud Run · Cloud Storage (GCS FUSE) · Gemini 3.5 Flash</text>

  <!-- ==================== 1. CLIENT LAYER ==================== -->
  <rect x="40" y="95" width="310" height="585" rx="10" fill="url(#gradClient)" stroke="#334155" stroke-width="1.5" filter="url(#shadow)"/>
  <rect x="40" y="95" width="310" height="36" rx="10" fill="#1e293b" />
  <rect x="40" y="121" width="310" height="10" fill="#1e293b" />
  <text x="56" y="119" fill="#38bdf8" font-size="13" font-weight="700">CLIENT LAYER: Browser SPA (React + Vite)</text>

  <!-- Client Box 1: Role Cockpit -->
  <rect x="56" y="145" width="278" height="95" rx="6" fill="url(#gradBox)" stroke="#475569" stroke-width="1"/>
  <text x="70" y="168" fill="#f1f5f9" font-size="13" font-weight="600">Role-Based Incident Cockpit</text>
  <text x="70" y="188" fill="#94a3b8" font-size="11.5">• Recall Coordinator (Simulate Signal, Propose Scope)</text>
  <text x="70" y="206" fill="#94a3b8" font-size="11.5">• QA Lead (Firm Quarantine Sign-Off)</text>
  <text x="70" y="224" fill="#94a3b8" font-size="11.5">• Customer Ops (Outbox Dispatch, Attestations)</text>

  <!-- Client Box 2: Dual Signature Rail -->
  <rect x="56" y="255" width="278" height="95" rx="6" fill="url(#gradBox)" stroke="#00dc82" stroke-width="1"/>
  <text x="70" y="278" fill="#00dc82" font-size="13" font-weight="600">Dual-Signature Release Rail</text>
  <text x="70" y="298" fill="#cbd5e1" font-size="11.5">Step 1: QA Lead Biological Clearance (Re-test Hash)</text>
  <text x="70" y="316" fill="#cbd5e1" font-size="11.5">Step 2: Closure Authority Operational Release</text>
  <text x="70" y="334" fill="#94a3b8" font-size="11">• 21 CFR § 7.49 Non-Response Escalation Modal</text>

  <!-- Client Box 3: Real-Time Stream -->
  <rect x="56" y="365" width="278" height="85" rx="6" fill="url(#gradBox)" stroke="#475569" stroke-width="1"/>
  <text x="70" y="388" fill="#f1f5f9" font-size="13" font-weight="600">Real-Time Event Consumer</text>
  <text x="70" y="408" fill="#94a3b8" font-size="11.5">• Server-Sent Events (SSE) stream subscriber</text>
  <text x="70" y="426" fill="#94a3b8" font-size="11.5">• 60s Ephemeral HMAC Token Authentication</text>
  <text x="70" y="442" fill="#94a3b8" font-size="11.5">• Automatic token refresh on reconnect</text>

  <!-- Client Box 4: Audit Inspector -->
  <rect x="56" y="465" width="278" height="85" rx="6" fill="url(#gradBox)" stroke="#475569" stroke-width="1"/>
  <text x="70" y="488" fill="#f1f5f9" font-size="13" font-weight="600">Audit Ledger &amp; Export Inspector</text>
  <text x="70" y="508" fill="#94a3b8" font-size="11.5">• Live tamper-evident ledger visualizer</text>
  <text x="70" y="526" fill="#94a3b8" font-size="11.5">• Instant cryptographic audit bundle download</text>
  <text x="70" y="542" fill="#94a3b8" font-size="11.5">• Client-side SHA-256 chain verification</text>

  <!-- Client Box 5: Geneology DAG -->
  <rect x="56" y="565" width="278" height="95" rx="6" fill="url(#gradBox)" stroke="#475569" stroke-width="1"/>
  <text x="70" y="588" fill="#f1f5f9" font-size="13" font-weight="600">Dynamic Genealogy DAG</text>
  <text x="70" y="608" fill="#94a3b8" font-size="11.5">• Contaminated lot ING-4417 isolation graph</text>
  <text x="70" y="626" fill="#94a3b8" font-size="11.5">• 200 Finished units (FP-A &amp; FP-B) quarantine</text>
  <text x="70" y="644" fill="#94a3b8" font-size="11.5">• 100 Negative control units (FP-C) unblocked</text>

  <!-- ==================== 2. COMPUTE LAYER (CLOUD RUN) ==================== -->
  <rect x="400" y="95" width="450" height="585" rx="10" fill="url(#gradCompute)" stroke="#38bdf8" stroke-width="1.5" filter="url(#shadow)"/>
  <rect x="400" y="95" width="450" height="36" rx="10" fill="#1e293b" />
  <rect x="400" y="121" width="450" height="10" fill="#1e293b" />
  <text x="416" y="119" fill="#38bdf8" font-size="13" font-weight="700">COMPUTE: Google Cloud Run (FastAPI + Kernel + Reducer)</text>

  <!-- FastAPI Gateway -->
  <rect x="420" y="145" width="410" height="75" rx="6" fill="url(#gradBox)" stroke="#475569" stroke-width="1"/>
  <text x="435" y="168" fill="#f1f5f9" font-size="13" font-weight="600">FastAPI Router &amp; SPA Static Server</text>
  <text x="435" y="188" fill="#94a3b8" font-size="11.5">• Routes: /api/evaluation/*, /api/projections/*, /api/cases/*</text>
  <text x="435" y="206" fill="#94a3b8" font-size="11.5">• Serves built Vite bundle (/assets) with SPA fallback to index.html</text>

  <!-- Authority Kernel -->
  <rect x="420" y="235" width="410" height="85" rx="6" fill="url(#gradBox)" stroke="#00dc82" stroke-width="1"/>
  <text x="435" y="258" fill="#00dc82" font-size="13" font-weight="600">Separation of Duties Authority Kernel</text>
  <text x="435" y="278" fill="#cbd5e1" font-size="11.5">• Strict separation: Requester != Approver (403 on role collision)</text>
  <text x="435" y="296" fill="#cbd5e1" font-size="11.5">• Dual-signature gate: QA Lead step 1 -> Closure Authority step 2</text>
  <text x="435" y="312" fill="#94a3b8" font-size="11">• 21 CFR § 7.49: >= 3 contact attempts + district office escalation</text>

  <!-- Deterministic Reducer & Optimistic Concurrency -->
  <rect x="420" y="335" width="410" height="85" rx="6" fill="url(#gradBox)" stroke="#475569" stroke-width="1"/>
  <text x="435" y="358" fill="#f1f5f9" font-size="13" font-weight="600">Deterministic Reducer Engine</text>
  <text x="435" y="378" fill="#94a3b8" font-size="11.5">• Pure state transition functions over domain event stream</text>
  <text x="435" y="396" fill="#94a3b8" font-size="11.5">• Optimistic concurrency: expected_version validation</text>
  <text x="435" y="412" fill="#94a3b8" font-size="11.5">• Zero hallucinated quantities or statuses; 100% deterministic math</text>

  <!-- Read Projections Engine -->
  <rect x="420" y="435" width="410" height="70" rx="6" fill="url(#gradBox)" stroke="#475569" stroke-width="1"/>
  <text x="435" y="458" fill="#f1f5f9" font-size="13" font-weight="600">Read-Model Projections Engine</text>
  <text x="435" y="478" fill="#94a3b8" font-size="11.5">• Query projections: Open Holds, Pending QA, Blocked Acknowledgements</text>
  <text x="435" y="494" fill="#94a3b8" font-size="11.5">• Fast event store indexing without full aggregate loading</text>

  <!-- Hash Chained Exporter & SSE Hub -->
  <rect x="420" y="520" width="195" height="140" rx="6" fill="url(#gradBox)" stroke="#a855f7" stroke-width="1"/>
  <text x="432" y="542" fill="#a855f7" font-size="12.5" font-weight="600">Hash-Chained Audit Exporter</text>
  <text x="432" y="562" fill="#94a3b8" font-size="11">• SHA-256 event chaining</text>
  <text x="432" y="578" fill="#94a3b8" font-size="11">• Top-level root digest</text>
  <text x="432" y="594" fill="#94a3b8" font-size="11">• Tamper detection: reorder,</text>
  <text x="432" y="610" fill="#94a3b8" font-size="11">  edit, omit, fake digest</text>
  <text x="432" y="626" fill="#94a3b8" font-size="11">• Self-verifying JSON bundle</text>

  <rect x="635" y="520" width="195" height="140" rx="6" fill="url(#gradBox)" stroke="#475569" stroke-width="1"/>
  <text x="647" y="542" fill="#f1f5f9" font-size="12.5" font-weight="600">Real-Time SSE Hub</text>
  <text x="647" y="562" fill="#94a3b8" font-size="11">• POST /api/sse-token</text>
  <text x="647" y="578" fill="#94a3b8" font-size="11">• 60s Ephemeral HMAC tokens</text>
  <text x="647" y="594" fill="#94a3b8" font-size="11">• Forgery &amp; expiry denial</text>
  <text x="647" y="610" fill="#94a3b8" font-size="11">• Live projection broadcast</text>
  <text x="647" y="626" fill="#94a3b8" font-size="11">• Non-blocking async queue</text>

  <!-- ==================== 3. EXTERNAL & CLOUD SERVICES ==================== -->
  
  <!-- AI Layer: Gemini 3.5 Flash -->
  <rect x="890" y="95" width="270" height="155" rx="8" fill="url(#gradCompute)" stroke="#38bdf8" stroke-width="1.5" filter="url(#shadow)"/>
  <rect x="890" y="95" width="270" height="32" rx="8" fill="#1e293b" />
  <rect x="890" y="117" width="270" height="10" fill="#1e293b" />
  <text x="905" y="117" fill="#38bdf8" font-size="12.5" font-weight="700">AI: Gemini 3.5 Flash (Google GenAI)</text>
  <text x="905" y="148" fill="#f1f5f9" font-size="12" font-weight="600">Multimodal Signal Extraction</text>
  <text x="905" y="168" fill="#94a3b8" font-size="11.5">• Ingests raw lab Salmonella notices</text>
  <text x="905" y="186" fill="#94a3b8" font-size="11.5">• Extracts lot ING-4417 &amp; pathogen</text>
  <text x="905" y="204" fill="#94a3b8" font-size="11.5">• Character-offset citation grounding</text>
  <text x="905" y="222" fill="#94a3b8" font-size="11.5">• Bound to source report SHA-256</text>

  <!-- Storage: Cloud Storage GCS FUSE -->
  <rect x="890" y="270" width="270" height="155" rx="8" fill="url(#gradCompute)" stroke="#00dc82" stroke-width="1.5" filter="url(#shadow)"/>
  <rect x="890" y="270" width="270" height="32" rx="8" fill="#1e293b" />
  <rect x="890" y="292" width="270" height="10" fill="#1e293b" />
  <text x="905" y="292" fill="#00dc82" font-size="12.5" font-weight="700">STORAGE: Google Cloud Storage (GCS)</text>
  <text x="905" y="323" fill="#f1f5f9" font-size="12" font-weight="600">GCS FUSE Mounted Volume</text>
  <text x="905" y="343" fill="#cbd5e1" font-size="11.5">• Mount: /app/data/lot_zero.db</text>
  <text x="905" y="361" fill="#cbd5e1" font-size="11.5">• Append-only table: incident_events</text>
  <text x="905" y="379" fill="#94a3b8" font-size="11.5">• UNIQUE(tenant_id, case_id, version)</text>
  <text x="905" y="397" fill="#94a3b8" font-size="11.5">• Max-instances: 1 (Single-writer safety)</text>

  <!-- Security: Secret Manager -->
  <rect x="890" y="445" width="270" height="110" rx="8" fill="url(#gradCompute)" stroke="#475569" stroke-width="1.5" filter="url(#shadow)"/>
  <rect x="890" y="445" width="270" height="32" rx="8" fill="#1e293b" />
  <rect x="890" y="467" width="270" height="10" fill="#1e293b" />
  <text x="905" y="467" fill="#cbd5e1" font-size="12.5" font-weight="700">SECURITY: Cloud Secret Manager</text>
  <text x="905" y="498" fill="#f1f5f9" font-size="12" font-weight="600">Runtime Secret Injection</text>
  <text x="905" y="518" fill="#94a3b8" font-size="11.5">• GEMINI_API_KEY:latest</text>
  <text x="905" y="536" fill="#94a3b8" font-size="11.5">• LOT_ZERO_SSE_SECRET:latest</text>

  <!-- Auditor Bundle -->
  <rect x="890" y="575" width="270" height="105" rx="8" fill="url(#gradCompute)" stroke="#a855f7" stroke-width="1.5" filter="url(#shadow)"/>
  <rect x="890" y="575" width="270" height="32" rx="8" fill="#1e293b" />
  <rect x="890" y="597" width="270" height="10" fill="#1e293b" />
  <text x="905" y="597" fill="#a855f7" font-size="12.5" font-weight="700">AUDITOR: Regulatory Bundle Export</text>
  <text x="905" y="628" fill="#f1f5f9" font-size="12" font-weight="600">Tamper-Evident Evidence Stream</text>
  <text x="905" y="648" fill="#94a3b8" font-size="11.5">• 21 CFR § 7.49 Non-Response Certified</text>
  <text x="905" y="666" fill="#94a3b8" font-size="11.5">• Verified SHA-256 Hash Chain Export</text>

  <!-- ==================== CONNECTORS ==================== -->
  <!-- Client to Gateway -->
  <line x1="350" y1="180" x2="420" y2="180" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrow)" />
  <text x="355" y="172" fill="#38bdf8" font-size="10" font-weight="600">HTTPS API</text>

  <!-- Client SSE to SSE Hub -->
  <line x1="350" y1="410" x2="635" y2="560" stroke="#38bdf8" stroke-width="2" stroke-dasharray="4" marker-end="url(#arrow)" />
  <text x="360" y="470" fill="#38bdf8" font-size="10" font-weight="600">SSE Stream</text>

  <!-- Gateway to AI -->
  <line x1="830" y1="170" x2="890" y2="170" stroke="#38bdf8" stroke-width="2" marker-end="url(#arrow)" />
  
  <!-- Reducer to Storage -->
  <line x1="830" y1="375" x2="890" y2="345" stroke="#00dc82" stroke-width="2" marker-end="url(#arrowGreen)" />

  <!-- Secrets to Compute -->
  <line x1="890" y1="500" x2="830" y2="470" stroke="#94a3b8" stroke-width="1.5" stroke-dasharray="3" />

  <!-- Exporter to Auditor -->
  <line x1="615" y1="620" x2="890" y2="620" stroke="#a855f7" stroke-width="2" marker-end="url(#arrowPurple)" />
</svg>
"""

with open(r"C:\Users\sujan reddy\Documents\john\lot-zero\docs\architecture.svg", "w", encoding="utf-8") as f:
    f.write(SVG_CONTENT)

print("Saved architecture vector diagram to docs/architecture.svg")
