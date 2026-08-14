# Lot Zero Google Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the local extraction and persistence adapters with a real Google ADK-orchestrated, Gemini-assisted, Firestore-checkpointed incident runtime while preserving deterministic authority and one-visible-effect recovery.

**Architecture:** One Python Cloud Run service receives authenticated Pub/Sub events and invokes one Google ADK orchestrator. Gemini generates bounded, cited candidates; registered ADK tools call the existing deterministic engine, policy gates, repositories, and idempotent synthetic adapters. Firestore owns durable application checkpoints and ledgers; ADK owns workflow and tool invocation, but no component is described as providing exactly-once execution.

**Tech Stack:** Python 3.12, Google ADK `2.5.0`, Gemini API/Vertex AI model `gemini-3.5-flash`, Google Gen AI SDK, Pydantic 2, FastAPI, Firestore, Pub/Sub, Cloud Storage, OpenTelemetry, pytest, Hypothesis, official Google Cloud emulators where supported.

## Global Constraints

- Before dependency installation, re-verify `google-adk==2.5.0`, Python compatibility, official ADK Runner/session/callback/function-tool APIs, and the contest-required Gemini model against current official sources; if an official source contradicts a pin, update this plan and record the citation in `docs/runtime-verification.md` before code.
- Runtime configuration pins `GEMINI_MODEL_ID=gemini-3.5-flash`; UI evidence displays model metadata returned by the live response or `Not available`, never a configured label presented as proof.
- The HTTP handler validates and registers events, then calls only `OrchestrationRuntime.run`; it never calls recall, policy, hold, notification, or closure services directly.
- Only `orchestration/adk_runtime.py`, `orchestration/agent.py`, and `orchestration/callbacks.py` may import Google ADK.
- Gemini handles cited extraction, bounded alias reconciliation, explanation, and drafting only. Deterministic code owns schema acceptance, graph traversal, dates/lots, quantities, transitions, permissions, policies, action keys, retries, and side effects.
- Tool arguments represent intent, not authority; every tool rechecks tenant, principal, phase, policy, approval, scope version, payload version/hash, and compare-and-set preconditions.
- Recipient PII, secrets, raw full notices, and notification recipient bodies never enter Gemini prompts, logs, or traces.
- Checkpoint/resume is Lot Zero application logic in Firestore, orchestrated through ADK; do not claim ADK exactly-once or Pub/Sub exactly-once.
- Local tests use scripted/replay model adapters. Only opt-in cloud smoke tests may support the claim that Gemini was used.
- Production has no fallback routine that manually replays the ADK tool sequence when ADK fails.

---

## File Map

```text
apps/api/
  pyproject.toml
  src/lot_zero/
    config.py
    telemetry.py
    api/{pubsub_models,events,approvals,health}.py
    persistence/{firestore_paths,case_repository,scope_repository}.py
    persistence/{action_ledger,evidence_ledger,checkpoint_repository}.py
    persistence/{approval_repository,outbox_repository,source_repository}.py
    integrations/{gemini_gateway,storage_source,inventory_adapter}.py
    integrations/{notification_sink,acknowledgements,failure_injection}.py
    orchestration/{contracts,execution_context,tool_models}.py
    orchestration/{tools,instructions,agent,adk_runtime,callbacks,service}.py
  tests/unit/{persistence,integrations,orchestration}/
  tests/integration/{emulators,adk,recovery}/
  tests/deployed/
fixtures/model-responses/*.json
scripts/emulators/{install.ps1,start.ps1,stop.ps1,verify.ps1}
docs/runtime-verification.md
```

### Task 1: Verify and pin the Google runtime surface

**Files:**
- Create: `docs/runtime-verification.md`
- Modify: `apps/api/pyproject.toml`
- Create: `apps/api/src/lot_zero/config.py`
- Test: `apps/api/tests/unit/test_config.py`

**Interfaces:**
- Produces: `Settings` with explicit `APP_ENV`, `GCP_PROJECT`, `GCP_REGION`, `GEMINI_MODEL_ID`, `ADK_EXPECTED_VERSION`, emulator hosts, model limits, and failure-injection flags.
- Produces: `RuntimeIdentity` reporting installed package version separately from configured model ID.

- [ ] **Step 1: Record first-party verification**

In `docs/runtime-verification.md`, record retrieval date, direct official URL, verified value, and implication for: ADK package/version and Python range; function tools/callbacks/Runner/session APIs; scripted test-model support; Gemini structured output/function calling/model identifier; Pub/Sub push envelope; Firestore transaction preconditions; emulator limits.

- [ ] **Step 2: Write failing settings tests**

```python
def test_demo_requires_explicit_project_region_and_model(monkeypatch):
    monkeypatch.setenv("APP_ENV", "demo")
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    with pytest.raises(ValidationError):
        Settings()

def test_failure_injection_is_forbidden_outside_eval_tenant():
    with pytest.raises(ValidationError):
        Settings(APP_ENV="demo", TENANT_ID="REAL", FAILURE_SCENARIO="notification.fail_before_effect")
```

- [ ] **Step 3: Pin dependencies and implement settings**

Pin exact released distributions for `google-adk==2.5.0`, Google Gen AI SDK, Firestore, Pub/Sub, Storage, auth, OpenTelemetry, FastAPI, Uvicorn, Pydantic, pytest, Ruff, and mypy. Fail startup on implicit cloud/emulator fallback, unknown environment, guessed model values, or enabled fault injection outside `EVAL-TENANT-01`.

- [ ] **Step 4: Verify dependency and settings integrity**

Run:

```powershell
python -m pytest apps/api/tests/unit/test_config.py -q
python -c "import importlib.metadata as m; print(m.version('google-adk'))"
```

Expected: tests pass and printed version equals the recorded pin.

- [ ] **Step 5: Commit**

```powershell
git add docs/runtime-verification.md apps/api/pyproject.toml apps/api/src/lot_zero/config.py apps/api/tests/unit/test_config.py
git commit -m "chore: pin verified Google agent runtime"
```

### Task 2: Implement tenant-safe Firestore paths and compare-and-set repositories

**Files:**
- Create: `apps/api/src/lot_zero/persistence/firestore_paths.py`
- Create: `apps/api/src/lot_zero/persistence/case_repository.py`
- Create: `apps/api/src/lot_zero/persistence/scope_repository.py`
- Create: `apps/api/src/lot_zero/persistence/checkpoint_repository.py`
- Test: `apps/api/tests/unit/persistence/test_paths.py`
- Test: `apps/api/tests/integration/emulators/test_case_repository.py`

**Interfaces:**
- Produces: `CaseRepository.register_signal`, `append_scope`, `compare_and_set_case`, `load_case`.
- Produces: `CheckpointRepository.load(run_id)` and `save(expected_sequence, checkpoint)`.

- [ ] **Step 1: Write path and concurrency tests**

```python
def test_record_id_cannot_escape_tenant_path():
    with pytest.raises(InvalidIdentifier):
        FirestorePaths.case("EVAL-TENANT-01", "../../other")

async def test_concurrent_scope_writers_create_one_next_version(repo):
    results = await asyncio.gather(*[repo.append_scope(scope_v2, expected_version=1) for _ in range(2)], return_exceptions=True)
    assert sum(isinstance(r, AffectedScope) for r in results) == 1
    assert sum(isinstance(r, StaleVersionError) for r in results) == 1
```

- [ ] **Step 2: Verify failure against the emulator**

Run: `.\scripts\emulators\start.ps1; python -m pytest apps/api/tests/integration/emulators/test_case_repository.py -q`

Expected: FAIL before repositories exist. If the verified emulator is unavailable, stop this task and document the exact missing dependency; do not replace it with a mock.

- [ ] **Step 3: Implement transactions and tenant-qualified paths**

Use `tenants/{tenant_id}/cases/{case_id}` and create-only scope documents with zero-padded versions. Registering the same stable domain event/hash returns the existing run; the same event ID with a different hash records a permanent conflict. A case transaction updates `state_revision`, `scope_version`, recovery status, return phase, and timestamps atomically.

- [ ] **Step 4: Run unit and emulator tests**

Run the path and repository test files. Expected: pass under contention with no partial writes.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero/persistence apps/api/tests scripts/emulators
git commit -m "feat: persist incidents with Firestore compare-and-set"
```

### Task 3: Add append-only evidence, approvals, and outbox repositories

**Files:**
- Create: `apps/api/src/lot_zero/persistence/evidence_ledger.py`
- Create: `apps/api/src/lot_zero/persistence/approval_repository.py`
- Create: `apps/api/src/lot_zero/persistence/outbox_repository.py`
- Test: `apps/api/tests/integration/emulators/test_evidence_ledger.py`
- Test: `apps/api/tests/integration/emulators/test_approval_repository.py`

**Interfaces:**
- Produces: `EvidenceLedger.append(entry) -> LedgerReceipt` with no update/delete method.
- Produces: `ApprovalRepository.record(decision)` and `consume(binding, expected_case_revision)`.

- [ ] **Step 1: Write hash-chain and stale-approval tests**

```python
async def test_ledger_verifies_from_genesis_to_head(ledger, entries):
    receipts = [await ledger.append(entry) for entry in entries]
    assert await ledger.verify_chain(receipts[-1].entry_hash)

async def test_payload_change_invalidates_approval(repo, approved_packet):
    with pytest.raises(StaleApprovalError):
        await repo.consume(approved_packet.binding(payload_hash="different"), expected_case_revision=4)
```

- [ ] **Step 2: Verify failure**

Run the two emulator test files. Expected: FAIL on missing repositories.

- [ ] **Step 3: Implement atomic evidence and approval semantics**

Append a canonical entry containing `prior_entry_hash`, compute `entry_hash`, create the ledger document, and CAS-update the case head in one transaction. Bind approvals to authenticated principal, role, requester, rationale, case revision, scope version, policy version, and optional payload version/hash; never silently rebind.

- [ ] **Step 4: Verify chain and race behavior**

Run the tests with concurrent writers. Expected: one correct total order, all stale approvals rejected, no update/delete repository API.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero/persistence apps/api/tests/integration/emulators
git commit -m "feat: persist evidence and version-bound approvals"
```

### Task 4: Implement the durable action ledger and ambiguous-result reconciliation

**Files:**
- Create: `apps/api/src/lot_zero/persistence/action_ledger.py`
- Create: `apps/api/src/lot_zero/integrations/notification_sink.py`
- Create: `apps/api/src/lot_zero/integrations/failure_injection.py`
- Test: `apps/api/tests/integration/recovery/test_action_ledger.py`

**Interfaces:**
- Produces: `reserve(intent) -> ActionReservation`, `lease(action_key, worker)`, `record_result`, and `resume(action_key)`.
- Produces: `NotificationSink.execute` and `reconcile`, keyed by provider token equal to the stable action key.

- [ ] **Step 1: Write concurrency, crash, and timeout tests**

```python
async def test_commit_then_timeout_reconciles_without_resend(harness):
    await harness.execute("notification.commit_then_timeout")
    assert (await harness.action()).state == "UNKNOWN"
    await harness.resume()
    assert harness.sink.execute_count == 1
    assert len(harness.sink.receipts) == 1
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest apps/api/tests/integration/recovery/test_action_ledger.py -q`

Expected: FAIL on missing action repository.

- [ ] **Step 3: Implement reservations, leases, and recovery**

Derive action keys from tenant, case, action type, target type/ID, scope version, policy ID, and payload hash. Persist `IN_FLIGHT` before adapter invocation. Reclaim expired leases only after reconciliation. Atomically persist result, checkpoint, evidence, and outbox records. Persist deterministic fault scenario ID, injection point, configured/observed count, and correlation ID.

- [ ] **Step 4: Verify one-visible-effect invariant**

Run the recovery suite for concurrent duplicate reservation, fail-before-effect, commit-then-timeout, crash-after-in-flight, and crash-after-provider-success. Expected: one provider receipt per action key.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero/persistence apps/api/src/lot_zero/integrations apps/api/tests/integration/recovery
git commit -m "feat: reconcile durable agent actions safely"
```

### Task 5: Build the bounded Gemini extraction gateway

**Files:**
- Create: `apps/api/src/lot_zero/integrations/storage_source.py`
- Create: `apps/api/src/lot_zero/integrations/gemini_gateway.py`
- Create: `fixtures/model-responses/scope-valid.json`
- Create: `fixtures/model-responses/scope-malformed.json`
- Test: `apps/api/tests/unit/integrations/test_gemini_gateway.py`
- Test: `apps/api/tests/deployed/test_live_gemini.py`

**Interfaces:**
- Produces: `GeminiGateway.extract_scope(source: PinnedSource) -> ExtractionResult`.
- Produces: `ModelEvidence` containing response-returned model/version metadata, response ID where available, request/response hashes, token counts, and citation validation result.

- [ ] **Step 1: Write citation, injection, and redaction tests**

```python
async def test_source_instruction_cannot_change_policy(gateway, injected_source):
    result = await gateway.extract_scope(injected_source)
    assert result.requested_tools == ()
    assert result.policy_mutations == ()

def test_citation_outside_pinned_generation_is_rejected(gateway):
    with pytest.raises(InvalidCitation):
        gateway.verify_span(span(char_end=10_000), pinned_source("short"))
```

- [ ] **Step 2: Verify failure with replay transport**

Run: `python -m pytest apps/api/tests/unit/integrations/test_gemini_gateway.py -q`

Expected: FAIL before gateway creation.

- [ ] **Step 3: Implement constrained structured extraction**

Fetch the exact Cloud Storage generation, verify SHA-256, delimit it as untrusted source data, request the strict extraction schema, cap input at 40,000 characters and output at 2,048 tokens, permit at most two schema-repair retries, validate page/character spans and excerpt hashes, and redact raw content from telemetry. Stop model calls when human evidence is required.

- [ ] **Step 4: Run replay tests; leave live test opt-in**

Run replay tests without credentials. Mark the deployed test with `@pytest.mark.cloud` and require it to assert runtime-returned model metadata, not merely the environment variable.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero/integrations fixtures/model-responses apps/api/tests
git commit -m "feat: add cited Gemini extraction boundary"
```

### Task 6: Define the narrow ADK tool surface and execution capability

**Files:**
- Create: `apps/api/src/lot_zero/orchestration/contracts.py`
- Create: `apps/api/src/lot_zero/orchestration/execution_context.py`
- Create: `apps/api/src/lot_zero/orchestration/tool_models.py`
- Create: `apps/api/src/lot_zero/orchestration/tools.py`
- Test: `apps/api/tests/unit/orchestration/test_tools.py`

**Interfaces:**
- Produces: `OrchestrationRuntime.run(signal, checkpoint) -> OrchestrationOutcome`.
- Produces: `AdkExecutionCapability(run_id, invocation_id, tool_call_id, tool_name, issued_at)`.
- Produces only these tools: `extract_scope`, `compute_recall_impact`, `request_provisional_holds`, `inspect_current_approvals`, `prepare_notification_packet`, `send_approved_notification`, `record_acknowledgement`, `create_sandbox_escalation`, `evaluate_closure`.

- [ ] **Step 1: Write capability and authority tests**

```python
async def test_tool_rejects_direct_call_without_adk_capability(tools):
    with pytest.raises(MissingAdkCapability):
        await tools.request_provisional_holds(request, capability=None)

async def test_model_arguments_cannot_broaden_tenant(tools, capability):
    with pytest.raises(AuthorizationDenied):
        await tools.compute_recall_impact(request.model_copy(update={"tenant_id": "OTHER"}), capability)
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest apps/api/tests/unit/orchestration/test_tools.py -q`

Expected: FAIL on missing tool registry.

- [ ] **Step 3: Implement capability-bound wrappers**

Require a current matching invocation/tool identity for every wrapper. Revalidate deterministic authority inside each tool. Persist ADK invocation ID, tool-call ID/name, input/output hashes, model response ID where applicable, action/state transition, actor class, run/correlation/trace IDs.

- [ ] **Step 4: Verify positive and negative tool calls**

Run the tool tests. Expected: allowed tools work once; direct, mismatched, stale, cross-tenant, forbidden, or malformed calls create no action.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero/orchestration apps/api/tests/unit/orchestration
git commit -m "feat: gate deterministic tools behind ADK execution"
```

### Task 7: Build the single ADK orchestrator and prove runtime ownership

**Files:**
- Create: `apps/api/src/lot_zero/orchestration/instructions.py`
- Create: `apps/api/src/lot_zero/orchestration/callbacks.py`
- Create: `apps/api/src/lot_zero/orchestration/agent.py`
- Create: `apps/api/src/lot_zero/orchestration/adk_runtime.py`
- Create: `apps/api/src/lot_zero/orchestration/service.py`
- Test: `apps/api/tests/integration/adk/test_real_runtime.py`
- Test: `apps/api/tests/unit/orchestration/test_import_boundaries.py`

**Interfaces:**
- Consumes: verified ADK APIs, registered tools, `GeminiGateway`, and durable checkpoints.
- Produces: one `lot_zero_orchestrator` and a production `AdkRuntime` implementation.

- [ ] **Step 1: Write static boundary and real-runtime tests**

```python
def test_http_layer_cannot_import_domain_actions(import_graph):
    assert import_graph.forbidden("lot_zero.api.events", {"lot_zero.domain.kernel", "lot_zero.integrations.notification_sink"}) == set()

async def test_no_adk_tool_event_means_no_hold_mutation(scripted_adk_runtime, repo):
    await scripted_adk_runtime.run(script=[])
    assert await repo.list_actions() == []
```

- [ ] **Step 2: Verify failure**

Run the boundary and ADK integration tests. Expected: FAIL before runtime modules exist.

- [ ] **Step 3: Implement the orchestrator through verified APIs**

The system instruction states the authority split, untrusted-source rule, allowed tools, evidence requirements, and stop conditions. Callbacks issue/revoke tool capabilities and write redacted audit events. Load checkpoints before each run; skip already completed tool calls by durable tool-call/action identity. ADK errors produce a durable recovery status, never a manual fallback sequence.

- [ ] **Step 4: Prove orchestration ownership**

Using the officially supported scripted test model, assert the ADK event stream contains a function call and response, the registered tool executes once, the evidence row contains matching invocation/tool-call IDs, direct wrapper calls fail, and a no-tool event stream makes no hold mutation.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero/orchestration apps/api/tests
git commit -m "feat: orchestrate Lot Zero with Google ADK"
```

### Task 8: Add the strict authenticated Pub/Sub event boundary

**Files:**
- Create: `apps/api/src/lot_zero/api/pubsub_models.py`
- Create: `apps/api/src/lot_zero/api/events.py`
- Modify: `apps/api/src/lot_zero/app.py`
- Test: `apps/api/tests/integration/emulators/test_pubsub_events.py`
- Test: `apps/api/tests/deployed/test_authenticated_push.py`

**Interfaces:**
- Produces: `POST /events` accepting the official Pub/Sub push envelope and invoking only `OrchestrationRuntime.run`.

- [ ] **Step 1: Write ingestion and retry-mapping tests**

```python
async def test_duplicate_delivery_ids_reuse_one_domain_run(client, envelope_factory):
    await client.post("/events", json=envelope_factory(message_id="A"))
    await client.post("/events", json=envelope_factory(message_id="B"))
    assert await count_runs_for("DOMAIN-EVENT-001") == 1
```

- [ ] **Step 2: Verify failure**

Run the Pub/Sub integration test. Expected: FAIL before endpoint implementation.

- [ ] **Step 3: Implement the thin event handler**

Verify production ingress identity/audience with the documented mechanism, base64-decode and strictly validate the signal, record delivery attempt/message/correlation/domain IDs, transactionally register or recognize the event, call only the runtime adapter, and return success after a durable checkpoint. Persist and acknowledge malformed permanent events; return retryable HTTP status only for retryable infrastructure/runtime failures.

- [ ] **Step 4: Verify duplicates and poison messages**

Run emulator tests for concurrent deliveries, malformed base64/schema, stable domain ID, and changed-payload conflict. Keep OIDC assertions exclusively in the deployed test.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero/api apps/api/src/lot_zero/app.py apps/api/tests
git commit -m "feat: ingest durable Pub/Sub incident signals"
```

### Task 9: Instrument correlation, redaction, and runtime evidence

**Files:**
- Create: `apps/api/src/lot_zero/telemetry.py`
- Modify: `apps/api/src/lot_zero/orchestration/callbacks.py`
- Modify: `apps/api/src/lot_zero/integrations/gemini_gateway.py`
- Test: `apps/api/tests/unit/test_telemetry.py`

**Interfaces:**
- Produces: structured log/span helpers propagating tenant, case, run, correlation, domain event, Pub/Sub message, scope, action, approval, payload hash, trace, revision, and Git SHA.

- [ ] **Step 1: Write redaction and propagation tests**

```python
def test_telemetry_never_contains_notice_or_recipient_body(captured_spans):
    serialized = json.dumps(captured_spans)
    assert "recipient@example" not in serialized
    assert "FULL NOTICE BODY" not in serialized
    assert "payload_hash" in serialized
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest apps/api/tests/unit/test_telemetry.py -q`

Expected: FAIL before telemetry helpers exist.

- [ ] **Step 3: Add named spans and structured events**

Instrument receive, source fetch, Gemini extraction, schema validation, reconciliation, genealogy, policy evaluation, action reservation/invocation/reconciliation, checkpoint save/resume, approval validation, notification retry, acknowledgement, closure evaluation, and outbox publish. Actor class is one of `gemini`, `deterministic`, `human`, or `provider`.

- [ ] **Step 4: Verify redaction and linkage**

Run telemetry and hero integration tests. Expected: every event shares correlation/run/case IDs; no raw source, prompt, output, recipient, or secret appears.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero apps/api/tests/unit/test_telemetry.py
git commit -m "feat: record redacted agent runtime evidence"
```

### Task 10: Prove emulator recovery parity and expose honest UI metadata

**Files:**
- Create: `apps/api/tests/integration/recovery/test_full_agent_run.py`
- Modify: `apps/api/src/lot_zero/domain/selectors.py`
- Modify: `contracts/incident-api.schema.json`
- Modify: `apps/web/src/api/schemas.ts`
- Test: `apps/web/tests/unit/runtime-proof.test.tsx`
- Modify: `README.md`

**Interfaces:**
- Produces: `RuntimeProofProjection` with availability-wrapped model, ADK distribution/version, invocation/tool-call IDs, revision, trace, delivery, run, and correlation values.

- [ ] **Step 1: Write parity and UI honesty tests**

```python
async def test_emulator_agent_run_matches_local_golden(agent_harness, golden):
    result = await agent_harness.run_complete_scenario()
    assert result.affected_record_ids == golden.affected_record_ids
    assert result.sink_receipt_count == 1
    assert result.closure.status == "BLOCKED"
```

- [ ] **Step 2: Verify failure**

Run the new recovery and web runtime-proof tests. Expected: FAIL before projection expansion.

- [ ] **Step 3: Complete the emulator hero run and projections**

Publish through the emulator, execute through the actual ADK runtime with scripted model, persist Firestore checkpoints, inject failure, restart the worker, reconcile, and finish blocked closure. Project only persisted runtime evidence; if a field is unsupported locally, return `unavailable` with a status record.

- [ ] **Step 4: Run the Google-runtime verification gate**

Run:

```powershell
.\scripts\emulators\verify.ps1
python -m pytest apps/api/tests -m "not cloud" -q
npm --prefix apps/web test
```

Expected: all non-cloud tests pass and the local golden outcome matches the emulator/ADK outcome.

- [ ] **Step 5: Commit**

```powershell
git add apps contracts README.md
git commit -m "test: prove ADK runtime recovery parity"
```

## Exit Gate

This plan is complete only when the real pinned ADK runtime owns tool invocation in an integration test, Gemini’s boundary is citation-checked and replay-tested, Firestore preserves versioned state and application checkpoints, duplicate/concurrent delivery yields one visible adapter effect, every authority check remains deterministic, and the UI labels unsupported local runtime proof as unavailable. Live-Gemini and authenticated-push claims remain pending until the deployed smoke plan passes.
