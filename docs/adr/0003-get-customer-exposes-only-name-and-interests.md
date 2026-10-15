# 3. get_customer exposes only name and interests, without authentication

## Context
Policy 4: customer data goes only to the customer, after email + password. But a shopper may ask for gift ideas for a friend who is a customer ("My friend is Michelle Garcia..."), which needs that friend's product interests.

## Decision
- `get_customer(email=None, name=None)` needs no password. At least one argument is required; if both are given they must match the same customer.
- Name matches the whole full name ("First Last"), case- and whitespace-insensitive. No partial or first-name-only matches.
- Returns only `full_name` and `product_interests`. Never email, password, age, or status.
- The schema tells the agent to use interests to pick products but not to recite them to anyone other than the authenticated customer.
- Status (premier) still comes only from `authenticate`.

## Consequences
- Anyone who knows a customer's name can steer recommendations by their interests; the raw list is protected only by agent instructions.
- Gift and "match my interests" queries work with one lookup.
