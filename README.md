# Lot Zero

Lot Zero is a deterministic, local evaluation slice for an evidence-backed food-recall incident workflow. It is deliberately bounded: it uses the fictional tenant `EVAL-TENANT-01`, version-controlled synthetic records, and a demo sink that performs no real outreach.

## Local contract

The versioned API wire contract is [contracts/incident-api.schema.json](contracts/incident-api.schema.json). Its canonical identifier is `https://lot-zero.local/contracts/incident-api/v1` and it is shared by the Python API and TypeScript client.

Every visible operational value must identify the records backing it. Where a value cannot be obtained locally, the contract requires an explicit unavailable status instead of a decorative placeholder. The persistent environment label is exactly:

`Evaluation tenant · synthetic records · no real outreach`

## Prerequisites

- Python 3.12
- Node.js and npm

Install API development dependencies and run the contract check:

```powershell
python -m pip install -e "./apps/api[dev]"
python -m pytest apps/api/tests/contract/test_schema.py -q
```

Install and build the protected Vite starter:

```powershell
npm install --prefix apps/web
npm --prefix apps/web run build
```

The starter accepts a local development server at port 4173:

```powershell
npm --prefix apps/web run dev -- --host 0.0.0.0 --port 4173 --strictPort
```
