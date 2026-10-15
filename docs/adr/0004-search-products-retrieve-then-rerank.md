# 4. search_products: retrieve 15, rerank with the Decisions API, return 10

## Context
Customers describe needs in natural language ("something to keep my coffee hot on the go", "something like the Eufy scale"). `filter_products` (ADR 0002) only applies hard constraints. Vector similarity alone (all-MiniLM-L6-v2 over name, category, description) finds the right neighborhood but ranks it loosely.

## Decision
- `search_products(query)`: one argument. The query is both the vector search phrase and the need the reranker judges.
- Retrieve the 15 nearest products from the Chroma index over the whole catalog, in stock or not.
- Rerank all 15 with one OpenAI Decisions API call (`client.decisions.create`, model `gpt-6-luna`, key `OPENAI_APY_KEY_DECISIONS`): a single `choice` question whose choices are the candidates (value = product id, description = the product's embedding text). Sort by each choice's probability, return the top 10.
- Ties, and candidates the answer omits (probability 0), keep retrieval order.
- If the call fails (OpenAI error, refusal, missing answer), return the top 10 in vector order with `relevance_probability: null` and a note. The agent always gets results.
- Each result is the priced product view plus `relevance_probability`. No threshold: always up to 10.
- Code layout: `tools/search_products/` is a package (`tool.py` contract and formatting, `pipeline.py` retrieve-then-rerank, `reranker.py` Decisions call). A tool becomes a package when it has private helpers. The vector index stays in `data_init/` because `load_store_data` builds it at startup.

## Consequences
- A choice question puts the probability mass on its few best picks; the rest come back near 0, so ranks beyond roughly 3 effectively follow vector order. Predicate (per-candidate) or score questions would grade every candidate, if that tail matters.
- Choice order can bias the probabilities (reported in the beta forum). Candidates are passed in retrieval order.
- Hard constraints are not enforced; the agent checks `available` and `customer_price`, or uses `filter_products`.
