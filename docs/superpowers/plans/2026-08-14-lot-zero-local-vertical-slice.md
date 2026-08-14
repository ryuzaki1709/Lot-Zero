# Lot Zero Local Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, locally runnable recall incident from signal through honestly blocked closure, with the selected Incident War Room UI driven entirely by persisted records.

**Architecture:** A Python 3.12 domain kernel is the single source of operational truth and is exposed through a small FastAPI boundary. In-memory repositories and synthetic adapters make the complete hero path reproducible without Google Cloud credentials; a React/Vite client consumes typed API projections and an SSE event stream without recalculating domain facts.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, pytest, Hypothesis, React 19, TypeScript, Vite, Zod, TanStack Query, Vitest, Testing Library, jest-axe, Playwright, Phosphor Icons, Source Serif 4, IBM Plex Sans.

## Global Constraints

- Live scenario data is fictional and tenant-scoped to `EVAL-TENANT-01`; no real company, recipient, domain, or private record may appear.
- The persistent header copy is exactly `Evaluation tenant · synthetic records · no real outreach`.
- Runtime IDs, hashes, counts, versions, timestamps, and statuses are returned by the running service or shown as `Not available`; none are decorative constants in React.
- Gemini performs no deterministic calculation in this plan. The local extractor is explicitly labeled `Fixture extraction replay`, never `Gemini`.
- Consequential steps use distinct scope, containment, notification, and closure approvals with role checks, rationale, version binding, and separation of duties.
- Delivery claims use `safe retry with one externally visible effect`, never `exactly once`.
- The selected visual reference is `C:\Users\sujan reddy\.codex\generated_images\019ffbc0-9eb0-7b43-b553-960c40b037b7\exec-5a581699-8b54-4b43-a8f9-0ffb3f56dbaa.png`.
- Use the Product Design web template bootstrap. Do not use Sites initialization, custom SVG, CSS art, emoji, gradients, glass, avatars, chatbot bubbles, or a generic dashboard shell.
- Visible icons come from Phosphor Icons; typography uses Source Serif 4 and IBM Plex Sans from locally bundled font files or their documented package source.
- The hero viewport is 1440×1024; below 760 CSS px or at 200% zoom, lanes become one semantic chronological list without two-axis application scrolling.
- No task may require cloud credentials, billing, Docker, `gcloud`, or live Gemini.

---

## File Map

```text
README.md                              local run and authenticity contract
apps/
  api/
    pyproject.toml                     Python dependency pins and tool config
    src/lot_zero/
      app.py                           FastAPI construction and route wiring
      api/{commands,events,models}.py  HTTP/SSE boundary
      domain/{models,commands,events,errors}.py
      domain/{kernel,reducer,transitions,policies}.py
      domain/{authority,ledger,selectors}.py
      fixtures/{loader,golden}.py
      ports/{repositories,actions,clock,ids}.py
      adapters/{memory_repository,demo_sink,fixture_extractor}.py
    tests/{unit,integration,contract}/
  web/
    package.json
    src/app/{App,IncidentProvider,useIncident}.tsx
    src/api/{client,schemas,sse}.ts
    src/features/war-room/*.tsx
    src/styles/{tokens,global,war-room}.css
    src/test/
    tests/{unit,a11y,e2e,visual}/
contracts/
  incident-api.schema.json             versioned JSON wire contract
fixtures/evaluation-tenant-v1/*.json   authored scenario and golden outcomes
scripts/{dev.ps1,verify-local.ps1}
design-qa.md                           blocking reference comparison report
```

### Task 1: Bootstrap the workspace and lock the local contract

**Files:**
- Create: `apps/web/*` with the Product Design bootstrap script
- Create: `apps/api/pyproject.toml`
- Create: `README.md`
- Create: `contracts/incident-api.schema.json`
- Test: `apps/api/tests/contract/test_schema.py`

**Interfaces:**
- Produces: JSON Schema `$id` `https://lot-zero.local/contracts/incident-api/v1`; top-level `IncidentProjection` and `CommandResponse` definitions.
- Produces: a versioned wire contract shared by the Python API and TypeScript client.

- [ ] **Step 1: Bootstrap the Product Design web template**

Run:

```powershell
node "C:\Users\sujan reddy\.codex\plugins\cache\openai-curated-remote\product-design\0.1.52\scripts\bootstrap-prototype.mjs" --dest apps/web
npm install --prefix apps/web
```

Expected: the protected Vite starter exists, `npm run dev -- --host 0.0.0.0 --port 4173 --strictPort` is accepted, and no Sites starter is created.

- [ ] **Step 2: Write the failing API contract test**

```python
def test_projection_requires_backing_record_ids(schema):
    projection = minimal_projection()
    projection["header"]["record_ids"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(projection, schema["$defs"]["IncidentProjection"])
```

- [ ] **Step 3: Add the schema and Python project configuration**

Define `Availability` as exactly one of `{kind: "available", value, record_ids}` or `{kind: "unavailable", reason, status_record_id}`. Pin Python to `>=3.12,<3.13`; configure pytest, Ruff, and mypy in `pyproject.toml`.

- [ ] **Step 4: Run the contract and starter checks**

Run:

```powershell
python -m pytest apps/api/tests/contract/test_schema.py -q
npm --prefix apps/web run build
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```powershell
git add README.md apps contracts
git commit -m "chore: bootstrap Lot Zero local workspace"
```

### Task 2: Publish the fictional fixture and human-reviewable golden outcomes

**Files:**
- Create: `fixtures/evaluation-tenant-v1/manifest.json`
- Create: `fixtures/evaluation-tenant-v1/signal.json`
- Create: `fixtures/evaluation-tenant-v1/operations.json`
- Create: `fixtures/evaluation-tenant-v1/golden.json`
- Create: `apps/api/src/lot_zero/fixtures/loader.py`
- Create: `apps/api/tests/unit/test_fixture.py`

**Interfaces:**
- Produces: `load_fixture(version: Literal["evaluation-tenant-v1"]) -> EvaluationFixture`.
- Produces: stable identifiers `EVAL-TENANT-01`, `ING-4417`, `FP-100`, `EVAL-HOLD-01`, and `EVAL-CLOSE-01`.

- [ ] **Step 1: Write fixture authenticity tests**

```python
def test_fixture_is_fictional_deterministic_and_complete(fixture):
    assert fixture.tenant_id == "EVAL-TENANT-01"
    assert fixture.signal.ingredient_lot == "ING-4417"
    assert fixture.clock_start.isoformat() == "2026-08-14T12:00:00+00:00"
    assert fixture.golden.outstanding_acknowledgement_ids == ("ACK-006",)
    assert not fixture.real_world_domains
```

- [ ] **Step 2: Run the test and confirm failure**

Run: `python -m pytest apps/api/tests/unit/test_fixture.py -q`

Expected: FAIL because `loader.py` and fixture files do not exist.

- [ ] **Step 3: Author and validate the fixture**

Include one affected ingredient lot, two affected finished lots, one adjacent unaffected batch, six synthetic recipients, five acknowledgements, one outstanding acknowledgement, a broken genealogy edge, and exact expected quantities. Record SHA-256 hashes in `manifest.json` and reject any mismatched file at load time.

- [ ] **Step 4: Run the fixture test**

Run: `python -m pytest apps/api/tests/unit/test_fixture.py -q`

Expected: PASS with no network access.

- [ ] **Step 5: Commit**

```powershell
git add fixtures apps/api/src/lot_zero/fixtures apps/api/tests/unit/test_fixture.py
git commit -m "test: publish deterministic evaluation fixture"
```

### Task 3: Implement strict domain records and canonical identifiers

**Files:**
- Create: `apps/api/src/lot_zero/domain/models.py`
- Create: `apps/api/src/lot_zero/domain/commands.py`
- Create: `apps/api/src/lot_zero/domain/events.py`
- Create: `apps/api/src/lot_zero/domain/errors.py`
- Create: `apps/api/src/lot_zero/domain/identifiers.py`
- Test: `apps/api/tests/unit/test_models.py`
- Test: `apps/api/tests/unit/test_identifiers.py`

**Interfaces:**
- Produces: strict Pydantic records `RecallCase`, `EvidenceSpan`, `AffectedScope`, `ImpactRecord`, `ContainmentAction`, `ApprovalDecision`, `NotificationPacket`, `Acknowledgement`, `LedgerEntry`, and `IncidentState`.
- Produces: `canonical_sha256(value: JsonValue) -> str` and `action_key(intent: ActionIntent) -> str`.

- [ ] **Step 1: Write strictness and hashing tests**

```python
def test_action_key_ignores_dictionary_order(intent_dict):
    assert action_key(ActionIntent(**intent_dict)) == action_key(
        ActionIntent(**dict(reversed(intent_dict.items())))
    )

def test_naive_timestamp_and_unknown_field_are_rejected():
    with pytest.raises(ValidationError):
        RecallCase.model_validate({**valid_case(), "updated_at": "2026-08-14T12:00:00", "fake": 1})
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest apps/api/tests/unit/test_models.py apps/api/tests/unit/test_identifiers.py -q`

Expected: FAIL on missing models and functions.

- [ ] **Step 3: Implement the records and canonical hashing**

Use `ConfigDict(extra="forbid", frozen=True)`, timezone-aware datetimes, `Decimal` quantities, discriminated unions for events/commands, and sorted compact UTF-8 JSON for SHA-256. Exclude Pub/Sub delivery IDs and retry counters from action keys.

- [ ] **Step 4: Verify pass and types**

Run:

```powershell
python -m pytest apps/api/tests/unit/test_models.py apps/api/tests/unit/test_identifiers.py -q
python -m mypy apps/api/src
```

Expected: PASS with no untyped definitions.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero/domain apps/api/tests/unit
git commit -m "feat: define strict incident domain records"
```

### Task 4: Build the deterministic recall engine and versioned scope delta

**Files:**
- Create: `apps/api/src/lot_zero/domain/recall.py`
- Create: `apps/api/src/lot_zero/domain/genealogy.py`
- Create: `apps/api/src/lot_zero/domain/scope.py`
- Test: `apps/api/tests/unit/test_recall.py`
- Test: `apps/api/tests/unit/test_recall_properties.py`

**Interfaces:**
- Consumes: `AffectedScope`, fixture product/genealogy/inventory/shipment records.
- Produces: `compute_impact(scope, product_master, genealogy, inventory, shipments) -> RecallImpact`.
- Produces: `compute_scope_delta(previous: RecallImpact, current: RecallImpact) -> ScopeDelta`.

- [ ] **Step 1: Write golden and property tests**

```python
def test_adjacent_batch_is_not_affected(fixture):
    impact = compute_impact(*fixture.recall_inputs)
    adjacent = next(r for r in impact.records if r.record_id == "FP-100-ADJ")
    assert adjacent.affected is False

@given(nonmatching_lot=st.from_regex(r"ING-[0-9]{4}", fullmatch=True).filter(lambda x: x != "ING-4417"))
def test_nonmatching_lot_never_passes_exact_lot_predicate(nonmatching_lot):
    assert exact_lot_match("ING-4417", nonmatching_lot) is False
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest apps/api/tests/unit/test_recall.py apps/api/tests/unit/test_recall_properties.py -q`

Expected: FAIL on missing recall engine.

- [ ] **Step 3: Implement deterministic traversal**

Normalize aliases, apply explicit product/lot/date predicates, traverse the graph cycle-safely, preserve every genealogy path and predicate ID, sort output by record type then ID, and mark missing edges `unresolved` instead of guessing. Scope expansion emits only newly affected targets.

- [ ] **Step 4: Verify the golden result**

Run: `python -m pytest apps/api/tests/unit/test_recall.py apps/api/tests/unit/test_recall_properties.py -q`

Expected: PASS, including zero false holds against `golden.json`.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero/domain apps/api/tests/unit
git commit -m "feat: compute deterministic recall impact"
```

### Task 5: Enforce the state machine, authority, and policy gates

**Files:**
- Create: `apps/api/src/lot_zero/domain/transitions.py`
- Create: `apps/api/src/lot_zero/domain/policies.py`
- Create: `apps/api/src/lot_zero/domain/authority.py`
- Test: `apps/api/tests/unit/test_transitions.py`
- Test: `apps/api/tests/unit/test_policies.py`
- Test: `apps/api/tests/unit/test_authority.py`

**Interfaces:**
- Produces: `transition(state, event) -> IncidentState`.
- Produces: `evaluate_hold_policy(intent, state, now) -> PolicyDecision`.
- Produces: `authorize(command, principal, state) -> AuthorizationDecision`.

- [ ] **Step 1: Write the transition and authority matrix tests**

```python
@pytest.mark.parametrize("source,target", ALLOWED_PRIMARY_TRANSITIONS)
def test_allowed_primary_transition(source, target):
    assert transition(case_in(source), event_for(target)).case.phase == target

def test_scope_approval_does_not_authorize_notification(state):
    decision = authorize(send_notification(), qa_principal(), state_with_scope_approval(state))
    assert decision.code == "MISSING_NOTIFICATION_APPROVAL"
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest apps/api/tests/unit/test_transitions.py apps/api/tests/unit/test_policies.py apps/api/tests/unit/test_authority.py -q`

Expected: FAIL on missing policy functions.

- [ ] **Step 3: Implement explicit tables**

Implement primary phases and orthogonal recovery states exactly as specified. `EVAL-HOLD-01` must validate tenant, target type, maximum golden-fixture quantity, reversibility, and 30-minute expiry independently. Reject cross-tenant access, requester/approver equality, missing rationale, wrong roles, and stale case/scope/payload/policy versions before creating events.

- [ ] **Step 4: Verify forbidden operations are inert**

Run the three test files and assert every denial returns zero events and zero requested effects; closure remains unreachable with `ACK-006` outstanding.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero/domain apps/api/tests/unit
git commit -m "feat: enforce incident authority and policy gates"
```

### Task 6: Add the event-sourced kernel, ledger, and safe retry protocol

**Files:**
- Create: `apps/api/src/lot_zero/domain/kernel.py`
- Create: `apps/api/src/lot_zero/domain/reducer.py`
- Create: `apps/api/src/lot_zero/domain/ledger.py`
- Create: `apps/api/src/lot_zero/ports/repositories.py`
- Create: `apps/api/src/lot_zero/ports/actions.py`
- Create: `apps/api/src/lot_zero/adapters/memory_repository.py`
- Create: `apps/api/src/lot_zero/adapters/demo_sink.py`
- Test: `apps/api/tests/unit/test_kernel.py`
- Test: `apps/api/tests/integration/test_retry_resume.py`

**Interfaces:**
- Produces: `execute_command(state, command, context) -> CommandResult` and `rehydrate(events) -> IncidentState`.
- Produces: `IncidentRepository.append(case_id, expected_version, events)` with compare-and-set.
- Produces: `ActionAdapter.execute(intent)` and `ActionAdapter.reconcile(idempotency_token)`.

- [ ] **Step 1: Write retry, crash, and hash-chain tests**

```python
async def test_retry_reuses_payload_and_creates_one_receipt(harness):
    first = await harness.dispatch(fail_before_effect=True)
    second = await harness.resume()
    assert first.payload_hash == second.payload_hash
    assert first.idempotency_token == second.idempotency_token
    assert len(harness.sink.receipts) == 1
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest apps/api/tests/unit/test_kernel.py apps/api/tests/integration/test_retry_resume.py -q`

Expected: FAIL on missing kernel/repositories.

- [ ] **Step 3: Implement append, reservation, and reconciliation**

Use `PLANNED → IN_FLIGHT → SUCCEEDED | FAILED | UNKNOWN`. Persist attempt state before adapter invocation. On ambiguous response call `reconcile` before any retry. Link each ledger entry with `prior_entry_hash`; call it append-only by service policy. The deterministic demo sink fails the first configured call, keys receipts by idempotency token, and never performs real outreach.

- [ ] **Step 4: Verify restart behavior**

Run the tests twice from fresh fixture resets. Expected: identical final incident projection and exactly one sink receipt in both runs.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero apps/api/tests
git commit -m "feat: add resumable incident kernel and safe retries"
```

### Task 7: Expose commands, projections, and a live SSE stream

**Files:**
- Create: `apps/api/src/lot_zero/domain/selectors.py`
- Create: `apps/api/src/lot_zero/api/models.py`
- Create: `apps/api/src/lot_zero/api/commands.py`
- Create: `apps/api/src/lot_zero/api/events.py`
- Create: `apps/api/src/lot_zero/app.py`
- Test: `apps/api/tests/contract/test_projection_contract.py`
- Test: `apps/api/tests/integration/test_hero_api.py`

**Interfaces:**
- Produces: `GET /api/incidents/{case_id}`, `GET /api/incidents/{case_id}/events`, `POST /api/evaluation/reset`, and typed command endpoints under `/api/incidents/{case_id}/commands/*`.
- Produces: SSE events `{event: "incident.updated", id: sequence, data: IncidentProjection}`.

- [ ] **Step 1: Write the record-backing and hero API tests**

```python
def test_every_visible_projection_value_has_record_ids(client, seeded_case):
    projection = client.get(f"/api/incidents/{seeded_case}").json()
    assert_projection_is_record_backed(projection)

def test_runtime_metadata_is_unavailable_locally(client, seeded_case):
    metadata = client.get(f"/api/incidents/{seeded_case}").json()["runtime"]
    assert metadata["model"]["kind"] == "unavailable"
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest apps/api/tests/contract/test_projection_contract.py apps/api/tests/integration/test_hero_api.py -q`

Expected: FAIL before route creation.

- [ ] **Step 3: Implement thin HTTP handlers and selectors**

Handlers authenticate a fixed local evaluation principal header, validate commands, invoke the kernel, and return projections. React-facing selectors calculate header, chronology, truth rail, safe action, approval dossier, evidence ledger, trace graph rows, recovery receipt, and closure gate from records. SSE reconnect honors `Last-Event-ID`.

- [ ] **Step 4: Verify the full API path**

Run the contract/integration tests. Expected: reset → start → approvals → injected failure → resume → five acknowledgements → escalation → blocked closure passes without network access.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/src/lot_zero apps/api/tests
git commit -m "feat: expose record-backed incident API"
```

### Task 8: Generate and enforce the TypeScript client contract

**Files:**
- Create: `apps/web/src/api/schemas.ts`
- Create: `apps/web/src/api/client.ts`
- Create: `apps/web/src/api/sse.ts`
- Create: `apps/web/src/app/IncidentProvider.tsx`
- Create: `apps/web/src/app/useIncident.ts`
- Test: `apps/web/src/api/client.test.ts`

**Interfaces:**
- Consumes: JSON wire types from `contracts/incident-api.schema.json`.
- Produces: `incidentClient.get`, `incidentClient.command`, `subscribeToIncident`, and `useIncident()`.

- [ ] **Step 1: Write schema rejection and reconnect tests**

```ts
it("rejects decorative runtime metadata", () => {
  expect(() => IncidentProjectionSchema.parse(projectionWithUnbackedModel)).toThrow();
});

it("reconnects from the last persisted sequence", () => {
  const stream = subscribeToIncident("CASE-001", { lastEventId: "7" });
  expect(stream.requestHeaders["Last-Event-ID"]).toBe("7");
});
```

- [ ] **Step 2: Verify failure**

Run: `npm --prefix apps/web test -- src/api/client.test.ts`

Expected: FAIL on missing schemas/client.

- [ ] **Step 3: Implement validated fetch and SSE state**

Parse every response with Zod, keep server state in TanStack Query, use SSE only as invalidation/projection delivery, and expose network/disconnected states through backed status records. Do not copy domain calculations into TypeScript.

- [ ] **Step 4: Verify pass**

Run: `npm --prefix apps/web test -- src/api/client.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/src/api apps/web/src/app
git commit -m "feat: add validated incident client"
```

### Task 9: Recreate the Incident War Room shell and chronology

**Files:**
- Create: `apps/web/src/styles/tokens.css`
- Create: `apps/web/src/styles/global.css`
- Create: `apps/web/src/styles/war-room.css`
- Create: `apps/web/src/features/war-room/WarRoomPage.tsx`
- Create: `apps/web/src/features/war-room/PriorityHeader.tsx`
- Create: `apps/web/src/features/war-room/ScenarioSummary.tsx`
- Create: `apps/web/src/features/war-room/Chronology.tsx`
- Create: `apps/web/src/features/war-room/EventPacket.tsx`
- Test: `apps/web/tests/unit/chronology.test.tsx`

**Interfaces:**
- Consumes: `IncidentProjection` only.
- Produces: semantic ordered chronology with packet accessible names containing sequence, lane, actor, event type, and status.

- [ ] **Step 1: Write semantic chronology tests**

```tsx
it("keeps chronological DOM order across visual lanes", () => {
  render(<Chronology packets={outOfLaneOrderPackets} />);
  expect(screen.getAllByRole("listitem").map(node => node.dataset.sequence)).toEqual(["1", "2", "3"]);
});
```

- [ ] **Step 2: Verify failure**

Run: `npm --prefix apps/web test -- tests/unit/chronology.test.tsx`

Expected: FAIL on missing components.

- [ ] **Step 3: Implement measured desktop geometry**

Implement the 56px header, 112px summary, 286px truth-rail reservation, 148px sticky lane labels, 176–208px packets, 12px packet spacing, and 14–16px operational text. Use warm ivory, navy, oxblood, amber, and forest tokens. Use Phosphor status icons plus visible state words; no color-only state.

- [ ] **Step 4: Verify component behavior and build**

Run:

```powershell
npm --prefix apps/web test -- tests/unit/chronology.test.tsx
npm --prefix apps/web run build
```

Expected: PASS with no TypeScript errors.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/src apps/web/tests/unit
git commit -m "feat: build Incident War Room chronology"
```

### Task 10: Add the truth rail, proof drawer, approvals, and recovery receipt

**Files:**
- Create: `apps/web/src/features/war-room/IncidentTruthRail.tsx`
- Create: `apps/web/src/features/war-room/CurrentSafeAction.tsx`
- Create: `apps/web/src/features/war-room/EvidenceDrawer.tsx`
- Create: `apps/web/src/features/war-room/EvidenceLedgerView.tsx`
- Create: `apps/web/src/features/war-room/TraceabilityEvidence.tsx`
- Create: `apps/web/src/features/war-room/ApprovalDossier.tsx`
- Create: `apps/web/src/features/war-room/RecoveryReceipt.tsx`
- Test: `apps/web/tests/unit/evidence-drawer.test.tsx`
- Test: `apps/web/tests/unit/truth-rail.test.tsx`

**Interfaces:**
- Consumes: projection subtrees and server command functions only.
- Produces: a 400px non-modal drawer with focus entry/Escape/focus return and an idempotent sandbox escalation control.

- [ ] **Step 1: Write interaction and honesty tests**

```tsx
it("returns focus to the originating packet", async () => {
  await user.click(packet);
  expect(drawerHeading).toHaveFocus();
  await user.keyboard("{Escape}");
  expect(packet).toHaveFocus();
});

it("explains why closure is locked", () => {
  expect(screen.getByText(/ACK-006 remains outstanding/)).toBeVisible();
  expect(screen.getByText(/EVAL-CLOSE-01/)).toBeVisible();
});
```

- [ ] **Step 2: Verify failure**

Run: `npm --prefix apps/web test -- tests/unit/evidence-drawer.test.tsx tests/unit/truth-rail.test.tsx`

Expected: FAIL on missing views.

- [ ] **Step 3: Implement supporting modes**

Render source spans, typed claims, validation rules, graph rows, authenticated approvals, retry attempts, hashes, idempotency key, provider receipt, and state deltas from projections. Truncate long IDs visually and provide a labeled copy control for the full value. The escalation action creates an internal synthetic task only.

- [ ] **Step 4: Verify interaction tests**

Run the two test files. Expected: PASS, including permission-denied, unavailable metadata, failed receipt, and disconnected trace states.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/src/features apps/web/tests/unit
git commit -m "feat: add incident evidence and recovery views"
```

### Task 11: Add live-run controls, responsive reflow, and accessibility gates

**Files:**
- Create: `apps/web/src/features/war-room/EventSpine.tsx`
- Create: `apps/web/src/features/war-room/LiveRunAnnouncer.tsx`
- Create: `apps/web/src/features/war-room/SkipLink.tsx`
- Modify: `apps/web/src/styles/war-room.css`
- Test: `apps/web/tests/a11y/war-room.test.tsx`
- Test: `apps/web/tests/e2e/keyboard-and-reflow.spec.ts`

**Interfaces:**
- Produces: presentation-only `inspectedSequence`; it cannot issue domain commands.
- Produces: responsive semantic list below 760 CSS px and reduced-motion behavior.

- [ ] **Step 1: Write accessibility and replay-isolation tests**

```tsx
it("replay never invokes a domain command", async () => {
  await user.click(screen.getByRole("button", { name: /play incident visualization/i }));
  await advanceTimersByTimeAsync(5000);
  expect(commandSpy).not.toHaveBeenCalled();
});
```

- [ ] **Step 2: Verify failure**

Run: `npm --prefix apps/web test -- tests/a11y/war-room.test.tsx`

Expected: FAIL before controls and labels exist.

- [ ] **Step 3: Implement focus, announcements, and reflow**

Focus order is skip link → run controls → packets → safe action → truth rail → evidence. All controls are at least 44×44 CSS px. Announce only current step, retry, failure, and blocked state. Do not autoplay. At reduced motion, jump between states. At 320 CSS px and 200% zoom, remove lane offsets and avoid simultaneous horizontal/vertical application scrolling.

- [ ] **Step 4: Run automated accessibility checks**

Run:

```powershell
npm --prefix apps/web test -- tests/a11y/war-room.test.tsx
npm --prefix apps/web run test:e2e -- tests/e2e/keyboard-and-reflow.spec.ts
```

Expected: zero serious/critical axe violations and all keyboard/reflow assertions pass.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/src apps/web/tests
git commit -m "feat: make the War Room accessible and responsive"
```

### Task 12: Prove the full hero path and pass Product Design QA

**Files:**
- Create: `apps/web/tests/e2e/hero-path.spec.ts`
- Create: `apps/web/tests/visual/war-room.spec.ts`
- Create: `scripts/dev.ps1`
- Create: `scripts/verify-local.ps1`
- Create: `design-qa.md`
- Modify: `README.md`

**Interfaces:**
- Produces: one-command local verification and a `design-qa.md` whose final line is `final result: passed`.

- [ ] **Step 1: Write the browser hero-path test**

Drive reset, start, cited scope review, deterministic impact, provisional holds, QA containment approval, separate Customer Operations payload approval, injected failure, checkpoint resume with identical hash, five acknowledgements, one outstanding acknowledgement, sandbox escalation, and blocked closure. Reload after the injected failure and after acknowledgement five.

- [ ] **Step 2: Add visual checkpoints**

Capture 1440×1024 states for initial signal, provisional containment, open approval dossier, retryable failure, recovery receipt, and blocked closure; also capture the 760px boundary, 320 CSS px, 200% zoom, reduced motion, and focus-visible state.

- [ ] **Step 3: Run the complete verification script**

```powershell
.\scripts\verify-local.ps1
```

The script must run Ruff, mypy, pytest, Vitest, build, Playwright hero path, accessibility tests, and visual snapshots, stopping on the first nonzero exit code.

- [ ] **Step 4: Compare reference and prototype in one visual review input**

Open the selected reference and the latest 1440×1024 capture together. Record hierarchy, geometry, typography, lane rhythm, packet density, truth-rail prominence, focus, and responsive findings in `design-qa.md`; fix every P0/P1/P2 and repeat until the file ends `final result: passed`.

- [ ] **Step 5: Commit**

```powershell
git add README.md scripts apps/web/tests design-qa.md
git commit -m "test: verify the complete local incident experience"
```

## Exit Gate

The local slice is complete only when a fresh clone can run the full scenario without credentials, every visible operational claim resolves to a record, the retry produces one sink receipt, closure stays blocked by `ACK-006`, all automated checks pass, and Product Design QA records `final result: passed`.
