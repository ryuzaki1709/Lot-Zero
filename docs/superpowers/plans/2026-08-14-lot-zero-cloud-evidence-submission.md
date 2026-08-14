# Lot Zero Cloud Evidence and Submission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the verified Lot Zero build to Google Cloud with least privilege and bounded cost, prove every judge-facing claim with correlation-linked evidence, and produce a consistent four-minute hackathon submission package.

**Architecture:** Terraform owns persistent resources in one isolated synthetic-evaluation project. Immutable Cloud Run revisions host web, agent, and private demo sink services; authenticated Pub/Sub starts the run; Firestore, Cloud Storage, Logging, and Trace preserve state and proof. A scripted cloud evaluator executes the same golden scenario, collects a sanitized checksummed evidence bundle, and generates the metrics, claim-evidence table, demo runbook, and submission copy from runtime artifacts.

**Tech Stack:** Terraform, Google Cloud Run, Artifact Registry, Firestore Native, Pub/Sub, Cloud Storage, Vertex AI Gemini, Secret Manager, IAM, Cloud Logging/Monitoring/Trace, OpenTelemetry, PowerShell, Python evaluation scripts, Playwright.

## Global Constraints

- Do not provision billable resources until Google Cloud Console shows the free-trial credit as issued and the user explicitly approves cloud deployment.
- Never click or instruct the user to click `Upgrade` for this build. A budget alert is not a hard spending cap.
- Terraform manages persistent resources; `gcloud` is limited to authentication/project selection, immutable image build/push, signal publication, deployed-state queries, and evidence collection.
- Use one project `lot-zero-eval-<suffix>`, one region chosen only after model availability/cost preflight, environment `demo`, tenant `EVAL-TENANT-01`, and prefix `lot-zero-demo`.
- Every supported resource carries `app=lot-zero`, `environment=demo`, `data_class=synthetic`, and `managed_by=terraform` labels.
- Cloud Run min instances are `0`; initial maxima are agent `3`, web `2`, sink `1`; initial size is one vCPU/1 GiB; timeout is at most 300 seconds.
- Agent and sink are private. Web may be network-reachable only when all non-health endpoints verify user authentication.
- Images deploy by digest, never `latest`; service-account key files and broad `Owner`, `Editor`, or project-wide invoker grants are forbidden.
- Source storage is called versioned/recoverable, never immutable without a retention lock. The evidence ledger is append-only by service policy, not intrinsically immutable.
- Real public/customer outreach is forbidden. The demo sink and all scenario identities remain visibly synthetic.
- Claims are generated from persisted proof. Screenshots, configured labels, or animations alone never prove Pub/Sub, Gemini, ADK, Firestore mutation, retries, or deployment.
- If credit, quota, region, model, IAM, or deployment preflight fails, keep the verified local build intact and record the exact blocker; do not spend or broaden permissions to force progress.

---

## File Map

```text
infra/terraform/
  bootstrap/{versions,providers,variables,state-bucket,outputs}.tf
  demo/{versions,providers,variables,apis,artifact-registry}.tf
  demo/{service-accounts,iam,storage,firestore,pubsub}.tf
  demo/{cloud-run,secrets,observability,audit-logging,budget,outputs}.tf
  demo/terraform.tfvars.example
infra/iam/{runtime-custom-role,evaluator-custom-role}.yaml
infra/dashboards/incident-operations.json
infra/policy/*.rego
scripts/cloud/{preflight,bootstrap,build-and-push,deploy}.ps1
scripts/cloud/{smoke-test,reset-demo,publish-signal,collect-evidence,replay-dlq}.ps1
eval/{run_evaluations,run_cloud_evaluations,metrics,ablation,report}.py
eval/{fixtures,golden,cases,schemas}/
docs/evaluation/{methodology,latest-report,claim-evidence}.md
docs/demo/{four-minute-runbook,recording-checklist,architecture}.mmd
docs/demo/evidence-manifest.schema.json
artifacts/evidence/<run-id>/*
```

### Task 1: Build a no-spend cloud preflight gate

**Files:**
- Create: `scripts/cloud/preflight.ps1`
- Create: `scripts/cloud/preflight.tests.ps1`
- Create: `infra/terraform/demo/terraform.tfvars.example`
- Modify: `README.md`

**Interfaces:**
- Produces: a non-mutating preflight JSON record with account, project, billing/credit readiness, region, model availability, authenticated principal, quota checks, tool versions, Git SHA, and an `approved_to_provision` boolean.

- [ ] **Step 1: Write failing script tests**

```powershell
It 'blocks when issued credits are absent' {
  $result = Invoke-LotZeroPreflight -BillingFixture '.\fixtures\billing-no-credit.json'
  $result.approved_to_provision | Should -BeFalse
  $result.blockers | Should -Contain 'FREE_TRIAL_CREDIT_NOT_ISSUED'
}
```

- [ ] **Step 2: Run and confirm failure**

Run: `Invoke-Pester .\scripts\cloud\preflight.tests.ps1`

Expected: FAIL because the command does not exist.

- [ ] **Step 3: Implement read-only preflight**

Resolve absolute tool paths; query active identity/project/billing state, required APIs’ availability, regional model availability, quotas, Terraform/gcloud versions, and Git cleanliness. Never enable APIs, attach billing, create resources, or print tokens. Exit nonzero unless credit is visibly issued and every required value is explicit.

- [ ] **Step 4: Run fixture tests and save the current blocked result**

Run the Pester suite, then run preflight against the current account only when `gcloud` is installed. Expected today: a clean, explicit credit blocker rather than resource creation.

- [ ] **Step 5: Commit**

```powershell
git add scripts/cloud README.md infra/terraform/demo/terraform.tfvars.example
git commit -m "chore: gate cloud provisioning on no-spend preflight"
```

### Task 2: Bootstrap Terraform remote state without mixing ownership

**Files:**
- Create: `infra/terraform/bootstrap/versions.tf`
- Create: `infra/terraform/bootstrap/providers.tf`
- Create: `infra/terraform/bootstrap/variables.tf`
- Create: `infra/terraform/bootstrap/state-bucket.tf`
- Create: `infra/terraform/bootstrap/outputs.tf`
- Create: `scripts/cloud/bootstrap.ps1`
- Test: `infra/policy/bootstrap.rego`

**Interfaces:**
- Produces: one private, versioned, encrypted Terraform-state bucket and documented state migration.

- [ ] **Step 1: Write policy tests**

Reject bootstrap plans with public access, disabled uniform bucket-level access, unversioned state, force-destroy, or missing `managed_by=terraform` label.

- [ ] **Step 2: Verify policy failure**

Run the repository-selected Terraform policy test command against an empty plan fixture. Expected: FAIL until the module exists.

- [ ] **Step 3: Implement bootstrap configuration**

Pin Terraform and Google provider versions. Create only the state bucket with uniform access, public access prevention, versioning, encryption, lifecycle policy, and `force_destroy=false`. The project and billing attachment remain pre-existing and unmanaged.

- [ ] **Step 4: Add an approval-gated bootstrap script**

`bootstrap.ps1` must require a passing `preflight.json`, show `terraform plan`, require the user’s explicit approval in the active session before `apply`, migrate state to the bucket, and finish with a clean plan. It must never create or modify billing.

- [ ] **Step 5: Commit**

```powershell
git add infra/terraform/bootstrap infra/policy/bootstrap.rego scripts/cloud/bootstrap.ps1
git commit -m "infra: define protected Terraform state bootstrap"
```

### Task 3: Provision core APIs, storage, Firestore, and Artifact Registry

**Files:**
- Create: `infra/terraform/demo/versions.tf`
- Create: `infra/terraform/demo/providers.tf`
- Create: `infra/terraform/demo/variables.tf`
- Create: `infra/terraform/demo/apis.tf`
- Create: `infra/terraform/demo/artifact-registry.tf`
- Create: `infra/terraform/demo/storage.tf`
- Create: `infra/terraform/demo/firestore.tf`
- Test: `infra/policy/core-resources.rego`

**Interfaces:**
- Produces: required service APIs, `lot-zero` Docker repository, regional Firestore Native database, and versioned source bucket.

- [ ] **Step 1: Write infrastructure policy assertions**

Assert deletion protection on Firestore, public-access prevention/uniform access/versioning/seven-day soft delete on source storage, retention of the newest three object generations, deletion of older noncurrent versions after 30 days, and `disable_on_destroy=false` for APIs.

- [ ] **Step 2: Run validation before implementation**

Run `terraform validate` and policy tests. Expected: FAIL on missing resources.

- [ ] **Step 3: Define verified resources**

Enable Run, Artifact Registry, Cloud Build, Firestore, Pub/Sub, Storage, Secret Manager, Vertex AI, Logging, Monitoring, Trace/Telemetry, IAM, IAM Credentials, Service Usage, and optional Billing Budgets APIs. Use the preflight-selected region and no retention lock.

- [ ] **Step 4: Verify a no-change plan fixture**

Format, validate, and generate a plan JSON; assert no public bindings, force destruction, global multi-region database, or unversioned bucket.

- [ ] **Step 5: Commit**

```powershell
git add infra/terraform/demo infra/policy/core-resources.rego
git commit -m "infra: define Lot Zero cloud foundations"
```

### Task 4: Enforce least-privilege service identities and negative IAM tests

**Files:**
- Create: `infra/terraform/demo/service-accounts.tf`
- Create: `infra/terraform/demo/iam.tf`
- Create: `infra/iam/runtime-custom-role.yaml`
- Create: `infra/iam/evaluator-custom-role.yaml`
- Create: `scripts/cloud/verify-iam.ps1`
- Test: `infra/policy/iam.rego`

**Interfaces:**
- Produces: distinct `lot-zero-web`, `lot-zero-agent`, `lot-zero-sink`, `lot-zero-push`, `lot-zero-evaluator`, and provisioning identities with resource-scoped grants.

- [ ] **Step 1: Write forbidden-grant tests**

Reject `Owner`, `Editor`, service-account keys, `allUsers` on agent/sink, project-wide Run Invoker, web access to Firestore/Vertex, push access to web/sink, and sink access to Storage/Vertex/Pub/Sub.

- [ ] **Step 2: Verify failure**

Run IAM policy tests against an intentionally broad fixture. Expected: named denials for every forbidden grant.

- [ ] **Step 3: Implement exact identities and bindings**

Agent receives datastore user, Vertex user, log/trace/metric writer, source-bucket object viewer, named-secret access, required topic publishing, and sink invocation only. Web invokes agent and reads only its named session secret. Sink has datastore plus telemetry only. Push invokes agent only. Evaluator receives bounded publish/read/invoke permissions; reset remains application-scoped to `EVAL-TENANT-01`.

- [ ] **Step 4: Add deployed positive and negative checks**

Use service-account impersonation, never keys. Prove allowed calls succeed and web→Firestore, push→sink, sink→Storage, unsigned→agent, and cross-tenant application access fail with consistent denial behavior.

- [ ] **Step 5: Commit**

```powershell
git add infra/terraform/demo infra/iam infra/policy/iam.rego scripts/cloud/verify-iam.ps1
git commit -m "security: enforce least-privilege cloud identities"
```

### Task 5: Configure authenticated Pub/Sub push, bounded retries, and DLQ

**Files:**
- Create: `infra/terraform/demo/pubsub.tf`
- Create: `scripts/cloud/publish-signal.ps1`
- Create: `scripts/cloud/replay-dlq.ps1`
- Test: `apps/api/tests/deployed/test_pubsub_delivery.py`

**Interfaces:**
- Produces: `incident-signals`, `incident-signals-dlq`, authenticated push subscription, and DLQ inspection subscription.

- [ ] **Step 1: Write delivery evidence tests**

```python
def test_dlq_replay_changes_message_id_not_domain_event_id(cloud_run):
    first, replay = cloud_run.exercise_dlq_replay()
    assert first.pubsub_message_id != replay.pubsub_message_id
    assert first.domain_event_id == replay.domain_event_id
```

- [ ] **Step 2: Validate the empty resource plan**

Expected: deployed test is skipped without cloud marker; Terraform policy test fails until topics/subscriptions exist.

- [ ] **Step 3: Define push and DLQ resources**

Use a dedicated OIDC push identity, 10-second minimum and 300-second maximum exponential retry, approximately five delivery attempts, seven-day retention, DLQ publisher/subscriber grants required by the verified Pub/Sub service-agent rules, and an inspection pull subscription.

- [ ] **Step 4: Verify configured and deployed behavior**

Policy-check retry/DLQ/OIDC fields. After deployment, prove authenticated push succeeds, unsigned direct `/events` fails, and replay preserves the stable domain ID while changing the delivery ID.

- [ ] **Step 5: Commit**

```powershell
git add infra/terraform/demo/pubsub.tf scripts/cloud apps/api/tests/deployed/test_pubsub_delivery.py
git commit -m "infra: add authenticated incident delivery and DLQ"
```

### Task 6: Build immutable Cloud Run web, agent, and demo-sink revisions

**Files:**
- Create: `apps/api/Dockerfile`
- Create: `apps/web/Dockerfile`
- Create: `apps/sink/Dockerfile`
- Create: `apps/sink/src/*`
- Create: `infra/terraform/demo/cloud-run.tf`
- Create: `infra/terraform/demo/secrets.tf`
- Create: `scripts/cloud/build-and-push.ps1`
- Create: `scripts/cloud/deploy.ps1`
- Test: `apps/api/tests/deployed/test_service_boundaries.py`

**Interfaces:**
- Produces: digest-addressed services `lot-zero-web`, `lot-zero-agent`, and `lot-zero-demo-sink` with probes and runtime metadata.

- [ ] **Step 1: Write image/revision and service-boundary tests**

Assert non-root containers, pinned base-image digest after verification, health/startup behavior, private agent/sink, max instances, required revision/Git/ADK/model settings, and a synthetic sink receipt keyed by idempotency token.

- [ ] **Step 2: Build locally and verify failure before Dockerfiles**

Run the selected container linter/build command. Expected: FAIL because Dockerfiles are missing.

- [ ] **Step 3: Implement minimal production images and services**

Build once per Git SHA, push to Artifact Registry, resolve immutable digests, and pass digests to Terraform. Configure Gen2, min `0`, maxima `2/3/1`, one vCPU/1 GiB, timeout ≤300 seconds, probes, service identities, runtime metadata, explicit `APP_ENV=demo`, and named secret references. No service-account keys or `latest` tag.

- [ ] **Step 4: Deploy only after explicit approval and passing preflight**

`deploy.ps1` rejects dirty Git, unpinned images, absent credit readiness, mismatched model/ADK pins, or failed local tests. It prints the Terraform plan for approval, applies it, and records output IDs/revisions without secrets.

- [ ] **Step 5: Commit**

```powershell
git add apps/*/Dockerfile apps/sink infra/terraform/demo scripts/cloud apps/api/tests/deployed
git commit -m "infra: deploy immutable Lot Zero services"
```

### Task 7: Add observability, audit controls, alerts, and cost guardrails

**Files:**
- Create: `infra/terraform/demo/observability.tf`
- Create: `infra/terraform/demo/audit-logging.tf`
- Create: `infra/terraform/demo/budget.tf`
- Create: `infra/dashboards/incident-operations.json`
- Modify: `apps/api/src/lot_zero/telemetry.py`
- Test: `apps/api/tests/deployed/test_observability.py`

**Interfaces:**
- Produces: correlation-linked traces/logs/metrics, a bounded dashboard, alerts, and optional budget notifications.

- [ ] **Step 1: Write observability and cost-policy tests**

Assert required spans and identifiers, prompt/PII redaction, demo trace sampling, min/max instances, bounded model calls (8), input characters (40,000), output tokens (2,048), repair retries (2), and budget thresholds at actual 50/80/100% plus forecast 100%.

- [ ] **Step 2: Verify policy failure**

Run infrastructure and deployed-test collection without cloud marker. Expected: Terraform policy fails until monitoring/cost resources exist; cloud tests remain explicitly skipped.

- [ ] **Step 3: Implement metrics and alerts**

Create counters/distributions for accepted signals, duplicate suppression, schema rejection, authorization denial, action terminal states, retries/reconciliation, DLQ, closure blockers, containment latency, and recovery latency. Alert on DLQ, retry exhaustion, denial spike, missing scheduled hold success, service error rate, and budget. Enable bounded Data Access audit logs and document their cost.

- [ ] **Step 4: Verify bounded evidence queries**

Run one synthetic cloud request and query only its correlation ID. Assert all required identifiers link across Pub/Sub, Run, Firestore, logs, and trace while raw notices/prompts/recipients remain absent.

- [ ] **Step 5: Commit**

```powershell
git add infra apps/api/src/lot_zero/telemetry.py apps/api/tests/deployed/test_observability.py
git commit -m "ops: add bounded telemetry and cost controls"
```

### Task 8: Build deterministic evaluation, ablation, and benchmark reports

**Files:**
- Create: `eval/metrics.py`
- Create: `eval/run_evaluations.py`
- Create: `eval/run_cloud_evaluations.py`
- Create: `eval/ablation.py`
- Create: `eval/report.py`
- Create: `eval/schemas/evaluation-report.schema.json`
- Create: `docs/evaluation/methodology.md`
- Test: `eval/tests/test_metrics.py`
- Test: `eval/tests/test_report.py`

**Interfaces:**
- Produces: `latest-report.json` and `latest-report.md` from raw case outcomes.
- Produces: precision/recall, false-hold rate, unresolved rate, citation precision/recall, duplicate prevention, one-visible-effect, acknowledgement coverage, containment/recovery latency, and ablation results.

- [ ] **Step 1: Write exact metric tests**

```python
def test_false_hold_rate():
    assert false_hold_rate(held_unaffected=1, golden_unaffected=20) == Decimal("0.05")

def test_zero_denominator_is_reported_not_hidden():
    assert precision(tp=0, fp=0).status == "not_applicable"
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest eval/tests -q`

Expected: FAIL before evaluation modules exist.

- [ ] **Step 3: Implement the versioned evaluation suite**

Cover exact match, adjacent batch, shared ingredient, missing mapping, ambiguous lot, duplicate/concurrent events, stale/out-of-order scope, delta expansion, restart, retry, ambiguous timeout, approval denial/race, late/missing acknowledgement, malformed output, prompt injection/exfiltration, forbidden tool, quota/DLQ, cross-tenant denial, and blocked closure. Preserve failures in reports.

- [ ] **Step 4: Add honest benchmarks and ablation**

Run ten clean resets and report median, p95, worst observed, scenario size, region, revision, and date. Compare deterministic-only versus Gemini-assisted candidate generation on identical authored cases with three model repetitions, fixed settings, and the same downstream validator. Do not generalize beyond the fixture.

- [ ] **Step 5: Commit**

```powershell
git add eval docs/evaluation/methodology.md
git commit -m "test: measure Lot Zero against golden outcomes"
```

### Task 9: Execute the correlation-linked cloud smoke run

**Files:**
- Create: `scripts/cloud/reset-demo.ps1`
- Create: `scripts/cloud/smoke-test.ps1`
- Create: `scripts/cloud/collect-evidence.ps1`
- Create: `docs/demo/evidence-manifest.schema.json`
- Test: `apps/api/tests/deployed/test_cloud_hero.py`

**Interfaces:**
- Produces: `artifacts/evidence/<run-id>/manifest.json` plus sanitized deployment, Pub/Sub, Firestore before/after, action/sink receipt, log, trace, model metadata, package version, and evaluation artifacts.

- [ ] **Step 1: Write manifest completeness tests**

```python
def test_claim_artifacts_share_one_correlation_id(bundle):
    ids = {artifact["correlation_id"] for artifact in bundle.runtime_artifacts}
    assert ids == {bundle.manifest.correlation_id}
```

- [ ] **Step 2: Verify failure on an empty bundle**

Run the manifest schema test with an empty fixture. Expected: FAIL listing every missing proof class.

- [ ] **Step 3: Implement the event-driven smoke runner**

Reset only `EVAL-TENANT-01`, capture Firestore before, publish a stable-domain-ID real Pub/Sub signal, poll persisted state rather than fixed sleeps, drive distinct approvals, inject one sink failure, prove identical payload hash/token on resume, record five acknowledgements, create the internal escalation, attempt closure, then redeliver the domain event to prove suppression.

- [ ] **Step 4: Collect and sanitize exact proof**

Collect project/region/services/revisions/digests, delivery/message/domain IDs, Gemini response metadata, ADK installed version/invocation/tool IDs, Firestore mutation, action/sink receipts, correlation/trace IDs, approvals, evaluation report, and checksums. Reject secrets, raw prompts, full notices, recipient data, mismatched correlation IDs, or unresolved artifact references.

- [ ] **Step 5: Commit scripts and schema; ignore raw bundles**

```powershell
git add scripts/cloud docs/demo/evidence-manifest.schema.json .gitignore apps/api/tests/deployed/test_cloud_hero.py
git commit -m "test: collect correlation-linked cloud proof"
```

### Task 10: Generate the claim-evidence table and architecture proof

**Files:**
- Create: `docs/evaluation/claim-evidence.md`
- Create: `docs/demo/architecture.mmd`
- Create: `eval/claim_evidence.py`
- Test: `eval/tests/test_claim_evidence.py`

**Interfaces:**
- Produces: exact artifact/test/record/trace links for every submission claim and a diagram separating Gemini, deterministic code, human authority, and the synthetic sink.

- [ ] **Step 1: Write claim-resolution tests**

Require proof for real Pub/Sub trigger, Gemini extraction, ADK orchestration, deterministic impact/policy, Firestore hold mutation, distinct approvals, one-visible-effect retry, duplicate suppression, blocked closure, tenant enforcement, GCP deployment, synthetic-only outreach, measured performance, and versioned storage.

- [ ] **Step 2: Verify failure against incomplete smoke evidence**

Expected: the generator fails by claim ID and missing artifact, not by generic validation error.

- [ ] **Step 3: Implement evidence generation**

Each row records claim, bounded wording, environment, test ID, artifact-relative path, persisted record ID, trace ID, and prohibited overclaim. Reject `exactly once`, `immutable`, `production SLA`, `certified compliance`, or real-outreach implications.

- [ ] **Step 4: Render and inspect the architecture diagram**

Show signal → authenticated Pub/Sub → ADK orchestrator → Gemini interpretation and deterministic tools → Firestore/action adapters → human approvals → private synthetic sink, with evidence/trace edges. Render Mermaid to SVG using a verified renderer; do not handcraft SVG.

- [ ] **Step 5: Commit**

```powershell
git add eval docs/evaluation/claim-evidence.md docs/demo/architecture.mmd
git commit -m "docs: link submission claims to runtime evidence"
```

### Task 11: Produce and rehearse the four-minute demo package

**Files:**
- Create: `docs/demo/four-minute-runbook.md`
- Create: `docs/demo/recording-checklist.md`
- Create: `scripts/cloud/demo-preflight.ps1`
- Create: `apps/web/tests/e2e/demo-recording-state.spec.ts`

**Interfaces:**
- Produces: a timed, reproducible four-minute recording sequence tied to one frozen revision and evidence bundle.

- [ ] **Step 1: Write recording-state assertions**

Assert 1440×1024 viewport, persistent synthetic label, no private/real recipient text, all visible IDs sharing the frozen correlation ID, model/ADK/revision values matching evidence, proof drawer initially closed, and blocked closure visible at the end.

- [ ] **Step 2: Create the exact timed script**

Use: `0:00–0:20` problem/authority boundary; `0:20–1:50` Pub/Sub through holds/approval; `1:50–2:35` injected failure/checkpoint/one receipt; `2:35–3:10` architecture/proof drawer; `3:10–3:40` metrics/Firestore/Run/PubSub/Trace; `3:40–4:00` outstanding acknowledgement/escalation/blocked closure.

- [ ] **Step 3: Freeze the recording inputs**

Record Git SHA, image digests, fixture manifest hash, model ID, ADK version, Cloud Run revisions, evidence-bundle checksum, browser version, viewport, and date. The fallback video, if needed, must use the same frozen revision and be labeled as such.

- [ ] **Step 4: Run two timed rehearsals and the recording gate**

`demo-preflight.ps1` reruns smoke proof checks, rejects stale/mismatched IDs, opens the verified War Room state, and emits a pass/fail checklist. Record only after two uninterrupted rehearsals finish under four minutes without hidden manual data changes.

- [ ] **Step 5: Commit**

```powershell
git add docs/demo scripts/cloud/demo-preflight.ps1 apps/web/tests/e2e/demo-recording-state.spec.ts
git commit -m "docs: prepare evidence-backed hackathon demo"
```

### Task 12: Assemble and consistency-check the Devpost submission

**Files:**
- Create: `docs/submission/devpost.md`
- Create: `docs/submission/README-submission.md`
- Create: `docs/submission/consistency-check.py`
- Test: `docs/submission/test_consistency.py`

**Interfaces:**
- Produces: final project story, setup/run instructions, architecture explanation, limitations, evidence links, image/video checklist, and copy-ready Devpost fields.

- [ ] **Step 1: Write cross-artifact consistency tests**

```python
def test_submission_uses_frozen_runtime_values(submission, manifest):
    assert submission.git_sha == manifest.git_sha
    assert submission.model_id == manifest.model_id
    assert submission.adk_version == manifest.adk_version
    assert submission.environment == "synthetic evaluation"
```

- [ ] **Step 2: Verify failure before submission copy exists**

Run: `python -m pytest docs/submission/test_consistency.py -q`

Expected: FAIL on missing submission files.

- [ ] **Step 3: Write the evidence-bounded submission**

Explain the real problem, why Taskmaster fits, what Gemini did, what ADK orchestrated, what deterministic code/humans controlled, GCP architecture, recovery proof, metrics, security/privacy, synthetic limitations, setup, and independent reproduction. Use the already approved name/elevator pitch and link each technical claim to `claim-evidence.md`.

- [ ] **Step 4: Run the complete release gate**

Run local verification, non-cloud tests, IaC validation/policy, cloud smoke, evaluation report, claim-evidence resolution, design QA, demo recording-state test, and submission consistency. All must pass against the same Git SHA and evidence manifest.

- [ ] **Step 5: Commit the submission package**

```powershell
git add docs/submission docs/evaluation docs/demo
git commit -m "docs: finalize Lot Zero hackathon submission"
```

## Exit Gate

This plan is complete only when cloud credit was visibly issued before provisioning, infrastructure is reproducible and least-privileged, the frozen deployment passes the full golden cloud run, every judge-facing claim resolves to sanitized persisted evidence under one correlation ID, Product Design QA remains passed, the four-minute demo rehearses reliably, and Devpost/README/video/diagram/report all agree on what is real, synthetic, simulated, and not claimed.
