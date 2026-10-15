# Assignment #4 — Sample Files

This gist contains the sample data sources, policies, queries, and helper scripts
for Assignment #4 (Agentic RAG). Your job is to build an agent, `hw4.py`, that
exposes a single function `answer_question(question: str) -> str` and answers
customer-support questions about a product catalog, customer records, and company
policies.

## Files in this gist

| File                      | Purpose                                                                 |
|---------------------------|-------------------------------------------------------------------------|
| `fetch_product_data.py`   | Downloads the real Walmart product dataset and shortens it to `product_data.csv` (787 rows). |
| `customers.json`          | 50 customer records (the customer database).                            |
| `data_init/customer_store.py` | Loads `customers.json` into an in-memory `cust_data` collection (mongomock). |
| `policies.txt`            | The 7 company policies your agent must enforce.                         |
| `example_queries.txt`     | 10 sample customer queries (illustrative only — see warning below).     |
| `prepare_dataset.py`      | Run once to verify all files are present and the data is ready.         |
| `README.md`               | This file.                                                              |

> Note: `product_data.csv` is **not** shipped in this gist — you generate it
> yourself by running `fetch_product_data.py` (see Setup).

## Setup

1. Download all 7 files from this gist into a single directory.

2. Install the dependencies:
   ```
   pip install kagglehub pandas mongomock chromadb sentence-transformers openai
   ```

3. Generate the product catalog:
   ```
   python fetch_product_data.py
   ```
   You should see:
   `Wrote product_data.csv with 787 rows (N guaranteed-keep).`

   **No Kaggle account or API key is required.** The script downloads the public
   dataset anonymously through `kagglehub`. You do not need to sign up, log in, or
   create a `kaggle.json`.

   *Fallback only:* in the rare case that Kaggle rate-limits anonymous downloads,
   create a free Kaggle account, go to Account → Create New API Token (this
   downloads `kaggle.json`), place it at `~/.kaggle/kaggle.json`, run
   `chmod 600 ~/.kaggle/kaggle.json`, and re-run the script. This is only a
   fallback — the normal path needs no credentials.

4. Verify everything is in place:
   ```
   python prepare_dataset.py
   ```
   You should see:
   `All required files found. You are ready to start working on hw4.py.`

5. Place your `hw4.py` (your agent) in the same directory and run it.

## The three data sources

1. **`product_data.csv`** — the authoritative product catalog (787 products,
   9 columns: `Uniq Id`, `Product Name`, `Description`, `List Price`,
   `Sale Price`, `Brand`, `Gtin`, `Category`, `Available`). Per company policy,
   this file is the authoritative source of product information — not the Internet.

2. **`customers.json` via `data_init/customer_store.py`** — 50 customer records. Each record
   has: `first_name`, `last_name`, `age`, `email`, `pw`, `status` (`premier` or
   `regular`), and `product-interests` (a list drawn from the 18 product-interest
   categories). Load them with:
   ```python
   from data_init.customer_store import get_cust_data_collection
   cust_data = get_cust_data_collection()
   ```
   `cust_data` is a standard pymongo-style collection supporting
   `find` / `find_one` / `count_documents`. **No MongoDB server and no Docker are
   required** — `mongomock` runs the collection entirely in memory, so your agent
   code is identical to what it would be against a real MongoDB.

3. **`policies.txt`** — the 7 company policies. Your agent must read and enforce
   them (authentication gate for customer data, 5% premier discount, the
   `$2000`/year premier threshold, the "no more than 3 suggestions" rule, the
   authoritative-CSV rule, and the exact "no product available" line).