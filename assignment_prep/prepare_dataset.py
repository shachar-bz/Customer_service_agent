#!/usr/bin/env python3
import os, sys, csv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Files may live next to this script (assignment_prep/) or one level up (repo root).
SEARCH_DIRS = [SCRIPT_DIR, os.path.dirname(SCRIPT_DIR)]
REQUIRED = ["fetch_product_data.py","customers.json",
            "policies.txt","example_queries.txt","README.md"]

def find_file(name):
    for directory in SEARCH_DIRS:
        path = os.path.join(directory, name)
        if os.path.exists(path):
            return path
    return None

def main():
    missing = [f for f in REQUIRED if find_file(f) is None]
    if missing: sys.exit(f"Missing gist files: {missing}")
    product_csv_path = find_file("product_data.csv")
    if product_csv_path is None:
        sys.exit("product_data.csv not found. Run: python fetch_product_data.py "
                 "(no Kaggle credentials needed — see README.md).")
    with open(product_csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, data = rows[0], rows[1:]
    need = ["Uniq Id","Product Name","Description","List Price","Sale Price",
            "Brand","Gtin","Category","Available"]
    if header[:9] != need: sys.exit(f"product_data.csv columns wrong: {header[:9]}")
    if len(data) != 787: sys.exit(f"product_data.csv has {len(data)} rows, expected 787.")
    sys.path.insert(0, os.path.dirname(SCRIPT_DIR))
    from data_init import customer_store
    n = customer_store.get_cust_data_collection().count_documents({})
    if n != 50: sys.exit(f"customers.json has {n} records, expected 50.")
    print("All required files found. You are ready to start working on hw4.py.")
if __name__ == "__main__":
    main()
