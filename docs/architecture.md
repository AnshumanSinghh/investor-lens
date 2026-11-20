# Architecture

## Layers and the dependency rule

```
domain  <-  application  <-  infrastructure / config  <-  bootstrap / cli
```

| Layer | Contains | May import |
|---|---|---|
| `domain` | Models, calculators (DCF, valuation, risk maths), filter rules, allocators, parameters | itself only |
| `application` | Ports (`MarketDataGateway`, `ReportWriter`), pipeline, evaluation policy, market-context loader, use case | domain |
| `config` | Typed settings, environment loader | domain |
| `infrastructure` | yfinance adapter, throttle/retry decorator, report serializer/renderer/writer, logging, atomic file writes | domain, application, config |
| `bootstrap` | Composition root: the only module that knows every concrete class | everything below |
| `cli` | Argument parsing, exit codes | everything below |

`tests/architecture/test_layering.py` parses every source file and fails the build if an import points
outward. It also confines the `yfinance` import to its adapter and keeps I/O modules out of the domain.

## Data flow

```
CLI -> bootstrap -> GenerateMarketIntelligence
                       |
                       +-> AnalysisPipeline
                       |     1. MarketContextLoader: risk-free rate + benchmark returns (with fallbacks)
                       |     2. per ticker: gateway.fetch_asset -> rules -> EvaluationPolicy (verdict, score)
                       |     3. PortfolioAllocator: correlation matrix + risk-parity weights
                       |     -> PipelineReport (domain object)
                       |
                       +-> ReportWriter -> payload dict -> markdown + JSON -> atomic file write
```

## Patterns and where they live

| Pattern | Where | Why |
|---|---|---|
| Strategy + Template Method | `FilterRule`, `PortfolioAllocator`, `EvaluationPolicy` | Add investors or policies without touching the pipeline (Open/Closed) |
| Ports and Adapters | `application/ports.py` (`MarketDataGateway`, `NewsGateway`, `ReportWriter`) and `infrastructure/*` | The core never knows about Yahoo or the filesystem |
| Decorator | `ResilientGateway`, `ResilientNewsGateway` | Throttling and retries work for any source; one shared `RequestGovernor` keeps the spacing global across price and news calls |
| Factory | `snapshot_factory.build_asset_snapshot` | Isolates vendor payload quirks from the domain model |
| Builder | `CheckCollector`, `PayloadBuilder` | Step-wise assembly of rule results and report payloads |
| Dependency Injection | constructors everywhere, wired in `bootstrap.py` | Tests inject fakes; no globals |

## Extending the data model

`AssetSnapshot.statements` is a generic map of canonical annual series (`domain.constants.Statement`).
A new lens that needs another statement line adds a key and a vendor-label mapping in
`snapshot_factory.py`; the file source reads the same keys from `<TICKER>.json`. News is fetched by the
pipeline through the `NewsGateway` port and attached as `AssetSnapshot.news`, best-effort: a news failure
becomes a data note, never a failed ticker. An injected market-data gateway gets no hidden news calls.

## Error-handling policy

- Expected data problems (`DataUnavailableError`) are never retried and become a `DATA_UNAVAILABLE` verdict.
- Transient problems (`DataFetchError`) are retried with exponential backoff, then recorded.
- Checks are tri-state (`True` / `False` / `None`); `None` means *inconclusive* and yields
  `INSUFFICIENT_DATA`, never a silent pass or fail.
- Buffett and Marks rules gate; Dalio never disqualifies, it scales weights.
- Output is written atomically (temp file + replace), so readers never see a partial report.

## Testing strategy

- `tests/unit/` mirrors the package layout and uses in-memory fakes (`tests/support/`).
- `tests/integration/test_end_to_end.py` runs the real wiring and writer with only the vendor faked.
- `tests/integration/test_yfinance_live.py` is opt-in and the only test that touches the network.
- `tests/architecture/` enforces the layering rules.
