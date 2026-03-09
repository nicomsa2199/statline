from src.db import run_sql_file

run_sql_file("sql/001_schema.sql")
run_sql_file("sql/002_views.sql")

print("Database schema and views created successfully.")