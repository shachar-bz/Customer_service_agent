# Glossary

- **Customer status** — `regular` or `premier`, stored per customer in `customers.json`.
- **Premier discount** — fixed 5% (`PREMIER_DISCOUNT_RATE`) off every item for premier customers.
- **Sale price** — the product's current price; equals list price when the item is not on sale.
- **Customer price** — what this customer pays: sale price minus the premier discount, if any. Hard price constraints (e.g. "under $100") compare against this.
- **Priced product view** — the product fields price-aware tools return: id, name, brand, category, list price, sale price, on sale, customer price, available.
- **Conversation session** — per-conversation state; holds only whether the authenticated customer is premier.
- **Tool** — a capability the agent can call: a `{TOOL}_SCHEMA` for the LLM, a pydantic args model, and a plain function; `tools/base.py::execute_tool` validates then calls it.
- **Hard filter** — a constraint every returned product must satisfy (price bound, brand, category, name prefix, availability); `filter_products` ANDs all given constraints. Matching rules: ADR 0002.
- **Category level** — one `|`-separated piece of a product's category path, e.g. `Bathroom Scales` in `Health | Home Health Care | Bathroom Scales | Mechanical Scales`. The `|` is internal; callers pass level names only.
- **Calculator** — `calculator` tool; the agent does all arithmetic through it, never in its head. Evaluates via an AST whitelist (no `eval`); results rounded to 2 decimals.
- **Customer lookup** — `get_customer` by email and/or full name; returns only full name + product interests, no auth needed. Rules: ADR 0003.
