import pandas as pd

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)

path = "data/raw/FCDB_7_4_14.xlsx"
sheets = pd.read_excel(path, sheet_name=None, header=None)

for name, df in sheets.items():
    print("=" * 60)
    print("SHEET:", name, "| shape:", df.shape)
    print(df.head(12).to_string(max_colwidth=22))