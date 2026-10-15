# 2. filter_products matching rules

## Context
Customers state hard constraints ("under $100", "LHCER brand", "bathroom scales"). The LLM needs one deterministic tool that applies them exactly, without doing price math or guessing catalog strings. The catalog has 787 products, 489 category paths like `Health | Home Health Care | Bathroom Scales | Mechanical Scales`, and 643 brands.

## Decision
- All arguments are optional and every given constraint is ANDed. "X or Y" requests are handled by the agent calling the tool once per alternative.
- Price: four optional bounds (`max_price_exclusive` <, `max_price_inclusive` <=, `min_price_exclusive` >, `min_price_inclusive` >=), compared against the customer price (premier discount included, see ADR 0001). At most one bound per side, bounds >= 0, minimum <= maximum; violations are argument errors.
- `brand`: case-insensitive, trimmed, whole-string equality.
- `categories`: list of category levels; each must equal (case-insensitively) a whole `|`-separated level of the product's path. Fragments like "scale" match nothing.
- `name_contains`: case-insensitive prefix of the product name.
- `categories` and `name_contains` are set only when the customer explicitly names them (stated in the schema).
- `available`: defaults to true (in stock only); false searches the whole catalog.
- A call with no constraint (all omitted, available true) is an error.
- Returns at most 10 priced product views in catalog order, plus `total_matches`; a note asks for narrower constraints when truncated, or says nothing matched.

## Consequences
- Segment matching is precise but the LLM must use real level names; a wrong guess returns no matches rather than noise.
- Combining hard filters with semantic relevance (e.g. "scales under $100 that show lbs and kg") is out of scope here.
