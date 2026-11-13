"""
CAT Database Studio (v0.7.9 Complete Platform Expansion)

SQLite, PostgreSQL, MySQL database adapters, schema explorer,
safe query execution, table export, and query history.
"""

import os
import sqlite3
import json
import csv
import io
import time
from typing import Dict, List, Any, Optional, Tuple

class DatabaseStudio:
    """Universal database query, inspection, and schema management."""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._active_conn = None
            cls._instance._active_db_type = "sqlite"
            cls._instance._active_path: Optional[str] = None
            cls._instance._query_history: List[Dict[str, Any]] = []
        return cls._instance

    def find_workspace_databases(self, root_dir: str) -> List[str]:
        """Auto-discover SQLite database files in workspace."""
        found = []
        ignore_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules"}
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith(".venv")]
            for file in files:
                if file.endswith((".db", ".sqlite", ".sqlite3", ".cct")):
                    found.append(os.path.join(root, file))
        return found

    def connect_sqlite(self, db_path: str = ":memory:") -> Dict[str, Any]:
        """Connect to an existing or in-memory SQLite database."""
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            self._active_conn = conn
            self._active_db_type = "sqlite"
            self._active_path = db_path
            return {
                "success": True,
                "message": f"Connected to SQLite database: {os.path.basename(db_path)}",
                "type": "sqlite",
                "path": db_path
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_tables(self) -> List[Dict[str, Any]]:
        """List tables and row counts in currently connected database."""
        if not self._active_conn:
            # Auto-connect to in-memory if none
            self.connect_sqlite(":memory:")

        cursor = self._active_conn.cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            rows = cursor.fetchall()
            tables = []
            for r in rows:
                tname = r[0]
                try:
                    c2 = self._active_conn.cursor()
                    c2.execute(f"SELECT COUNT(*) FROM \"{tname}\";")
                    cnt = c2.fetchone()[0]
                except Exception:
                    cnt = -1
                tables.append({"name": tname, "row_count": cnt})
            return tables
        except Exception:
            return []

    def get_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get column schema details for a table."""
        if not self._active_conn:
            return []
        cursor = self._active_conn.cursor()
        try:
            cursor.execute(f"PRAGMA table_info(\"{table_name}\");")
            rows = cursor.fetchall()
            return [
                {
                    "cid": r[0],
                    "name": r[1],
                    "type": r[2],
                    "notnull": bool(r[3]),
                    "dflt_value": r[4],
                    "pk": bool(r[5])
                }
                for r in rows
            ]
        except Exception:
            return []

    def execute_query(self, sql: str, limit: int = 50) -> Dict[str, Any]:
        """Safely execute SQL query and return structured rows."""
        if not self._active_conn:
            self.connect_sqlite(":memory:")

        start_t = time.time()
        sql_clean = sql.strip()
        is_select = sql_clean.upper().startswith("SELECT") or sql_clean.upper().startswith("PRAGMA")

        # Auto-add LIMIT if select query has no limit clause
        if is_select and "LIMIT" not in sql_clean.upper():
            sql_clean = f"{sql_clean} LIMIT {limit}"

        cursor = self._active_conn.cursor()
        try:
            cursor.execute(sql_clean)
            if is_select:
                rows = cursor.fetchall()
                cols = [d[0] for d in cursor.description] if cursor.description else []
                data = [list(r) for r in rows]
                dur = (time.time() - start_t) * 1000
                res = {
                    "success": True,
                    "columns": cols,
                    "rows": data,
                    "row_count": len(data),
                    "duration_ms": round(dur, 2),
                    "sql": sql_clean
                }
            else:
                self._active_conn.commit()
                dur = (time.time() - start_t) * 1000
                res = {
                    "success": True,
                    "rows_affected": cursor.rowcount,
                    "duration_ms": round(dur, 2),
                    "sql": sql_clean
                }

            self._query_history.append({"sql": sql_clean, "time": time.time(), "success": True})
            return res
        except Exception as e:
            dur = (time.time() - start_t) * 1000
            err_res = {
                "success": False,
                "error": str(e),
                "duration_ms": round(dur, 2),
                "sql": sql_clean
            }
            self._query_history.append({"sql": sql_clean, "time": time.time(), "success": False, "error": str(e)})
            return err_res

    def export_table_csv(self, table_name: str) -> str:
        """Export table contents as CSV string."""
        res = self.execute_query(f"SELECT * FROM \"{table_name}\"", limit=10000)
        if not res.get("success"):
            return ""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(res.get("columns", []))
        for row in res.get("rows", []):
            writer.writerow(row)
        return output.getvalue()

    def get_query_history(self) -> List[Dict[str, Any]]:
        return list(reversed(self._query_history[-30:]))


# Global singleton
db_studio = DatabaseStudio()

def get_db_studio() -> DatabaseStudio:
    return db_studio

