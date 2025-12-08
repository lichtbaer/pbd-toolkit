"""SQLite database processor for extracting text from database files."""

import sqlite3
from typing import Iterator
from file_processors.base_processor import BaseFileProcessor


class SqliteProcessor(BaseFileProcessor):
    """Processor for SQLite database files.

    Extracts text content from all tables in the database.
    Handles text columns and optionally BLOB fields.
    """

    def extract_text(self, file_path: str) -> Iterator[str]:
        """Extract text from SQLite database.

        Args:
            file_path: Path to the SQLite database file

        Yields:
            Text content from database tables

        Raises:
            sqlite3.Error: If database cannot be accessed
            PermissionError: If file cannot be accessed
            FileNotFoundError: If file does not exist
        """
        try:
            conn = sqlite3.connect(file_path)
            cursor = conn.cursor()

            try:
                # Get all table names
                cursor.execute(
                    """
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """
                )
                tables = cursor.fetchall()

                for (table_name,) in tables:
                    try:
                        # Get column names for this table
                        cursor.execute(f"PRAGMA table_info({table_name})")
                        columns = cursor.fetchall()

                        # Build SELECT query for text columns
                        text_columns = []
                        for col in columns:
                            col_name = col[1]
                            col_type = col[2].upper() if col[2] else ""
                            # Include TEXT, VARCHAR, CHAR, and BLOB (may contain text)
                            if any(
                                t in col_type
                                for t in ["TEXT", "VARCHAR", "CHAR", "BLOB", ""]
                            ):
                                text_columns.append(col_name)

                        if not text_columns:
                            continue

                        # Select all text columns
                        columns_str = ", ".join(text_columns)
                        cursor.execute(f"SELECT {columns_str} FROM {table_name}")

                        rows = cursor.fetchall()
                        for row in rows:
                            row_text_parts = []
                            for i, value in enumerate(row):
                                if value is not None:
                                    # Try to decode if bytes (BLOB)
                                    if isinstance(value, bytes):
                                        try:
                                            value = value.decode("utf-8")
                                        except UnicodeDecodeError:
                                            try:
                                                value = value.decode("latin-1")
                                            except UnicodeDecodeError:
                                                # Skip binary BLOBs
                                                continue
                                    row_text_parts.append(str(value))

                            if row_text_parts:
                                yield f"[Table: {table_name}]\n" + " | ".join(
                                    row_text_parts
                                ) + "\n"
                    except sqlite3.Error:
                        # Skip tables that can't be read
                        continue
                    except Exception:
                        # Skip tables with errors
                        continue
            finally:
                conn.close()
        except sqlite3.Error:
            raise
        except Exception:
            raise

    @staticmethod
    def can_process(extension: str, file_path: str = "", mime_type: str = "") -> bool:
        """Check if this processor can handle the file.

        Args:
            extension: File extension
            file_path: Full path to the file
            mime_type: Detected MIME type

        Returns:
            True if file is a SQLite database, False otherwise
        """
        if extension.lower() in [".sqlite", ".sqlite3", ".db"]:
            return True

        if mime_type:
            return mime_type in [
                "application/x-sqlite3",
                "application/vnd.sqlite3",
                "application/x-sqlite",
            ]

        # Check file header if file_path is provided
        if file_path:
            try:
                with open(file_path, "rb") as f:
                    header = f.read(16)
                    # SQLite files start with "SQLite format 3"
                    if header.startswith(b"SQLite format 3"):
                        return True
            except Exception:
                pass

        return False
