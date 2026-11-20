# Sample data (synthetic)

Invented companies and random-walk prices for trying the tool offline. **Not real market data.**

```bash
investor-lens --source files --data-dir examples/data --tickers DEMOA,DEMOB --output out.md
```

See the header of `src/investor_lens/infrastructure/market_data/file_gateway.py` for the file format.
