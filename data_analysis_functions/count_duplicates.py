from pathlib import Path

import pandas as pd

root_path = Path(r"\data\2025-05-30\18-41-21")

# List all files in the directory
all_files = list(root_path.iterdir())

# Filter to only include CSV files (optional, if you only care about CSVs)
csv_files = [f for f in all_files if f.suffix == ".csv"]

# Read CSVs
dfs = [pd.read_csv(f) for f in csv_files]

# Use pandas hashing for comparison
hashes = [pd.util.hash_pandas_object(df, index=True).sum() for df in dfs]

# Count unique hashes
unique_hashes = set(hashes)
num_unique = len(unique_hashes)
num_duplicates = len(hashes) - num_unique

print(f"Total files: {len(dfs)}")
print(f"Unique DataFrames: {num_unique}")
print(f"Duplicate DataFrames: {num_duplicates}")
