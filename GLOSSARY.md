# Glossary

- **Customer status** — `regular` or `premier`, stored per customer in `customers.json`.
- **Premier discount** — fixed 5% (`PREMIER_DISCOUNT_RATE`) off every item for premier customers.
- **Sale price** — the product's current price; equals list price when the item is not on sale.
- **Customer price** — what this customer pays: sale price minus the premier discount, if any. Hard price constraints (e.g. "under $100") compare against this.
- **Priced product view** — the product fields price-aware tools return: id, name, brand, category, list price, sale price, on sale, customer price.
- **Conversation session** — per-conversation state; holds only whether the authenticated customer is premier.
- **Tool** — a capability the agent can call: a `{TOOL}_SCHEMA` for the LLM, a pydantic args model, and a plain function; `tools/base.py::execute_tool` validates then calls it.
