"""Run the SQL layers in order against DuckDB and export the golden dataset.
Usage: python src/run_pipeline.py [--raw data/raw] [--db outputs/collections.duckdb]
"""
import argparse, glob, os, duckdb

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="data/raw")
    ap.add_argument("--db", default="outputs/collections.duckdb")
    ap.add_argument("--out", default="data/golden")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.db), exist_ok=True); os.makedirs(a.out, exist_ok=True)
    if os.path.exists(a.db): os.remove(a.db)
    con = duckdb.connect(a.db)
    for f in sorted(glob.glob("sql/[0-9]*.sql")):
        sql = open(f).read().replace("${RAW}", a.raw.replace("\\", "/"))
        print("running", f); con.execute(sql)
    for (t,) in con.execute("select table_name from information_schema.tables where table_schema='golden'").fetchall():
        con.execute(f"COPY golden.{t} TO '{a.out}/{t}.csv' (HEADER, DELIMITER ',')")
        print("exported golden." + t, con.execute(f"select count(*) from golden.{t}").fetchone()[0], "rows")
    con.close()

if __name__ == "__main__":
    main()
