"""
Wrapper para SQLite con soporte de cifrado transparente de campos sensibles.
Proporciona funciones que cifran/descifran automáticamente datos específicos.

RS4: Cifrado en bases de datos
"""

import sqlite3
from pathlib import Path
from typing import Any, List, Tuple

from src.security.encryption import EncryptionManager


class EncryptedSQLiteConnection:
    """
    Envuelve conexión a SQLite y cifra/descifra automáticamente campos sensibles.

    Campos sensibles automáticos:
    - password (en tabla users)
    - refresh_token (en tabla tokens)
    - email (opcionalmente)

    Example:
        manager = EncryptionManager(key)
        conn = EncryptedSQLiteConnection("auth.db", manager)
        cursor = conn.cursor()
        # El cifrado/descifrado es transparente
    """

    # Campos que deben cifrarse en cada tabla
    ENCRYPTED_FIELDS = {
        "users": ["password"],  # No cifrar email para búsquedas
        "tokens": ["refresh_token"],
    }

    def __init__(
        self,
        db_path: Path | str,
        encryption_manager: EncryptionManager | None = None,
        auto_encrypt: bool = True
    ):
        """
        Inicializa conexión con soporte de cifrado opcional.

        Args:
            db_path: Ruta a la base de datos SQLite
            encryption_manager: EncryptionManager para cifrar/descifrar
            auto_encrypt: Si True, cifra/descifra automáticamente
        """
        self.db_path = Path(db_path)
        self.encryption_manager = encryption_manager
        self.auto_encrypt = auto_encrypt and encryption_manager is not None
        self.connection = sqlite3.connect(str(self.db_path))
        # Retornar diccionarios en lugar de tuplas
        self.connection.row_factory = sqlite3.Row

    def cursor(self):
        """Retorna un cursor con soporte de cifrado."""
        return EncryptedCursor(
            self.connection.cursor(),
            self.encryption_manager,
            self.auto_encrypt,
            self.ENCRYPTED_FIELDS
        )

    def commit(self):
        """Confirma cambios."""
        self.connection.commit()

    def rollback(self):
        """Revierte cambios."""
        self.connection.rollback()

    def close(self):
        """Cierra la conexión."""
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class EncryptedCursor:
    """
    Cursor que cifra/descifra automáticamente campos sensibles.

    Operaciones soportadas:
    - execute() / executemany()
    - fetchone() / fetchall() / fetchmany()
    - INSERT/UPDATE automáticamente cifra valores
    - SELECT automáticamente descifra valores
    """

    def __init__(
        self,
        cursor: sqlite3.Cursor,
        encryption_manager: EncryptionManager | None,
        auto_encrypt: bool,
        encrypted_fields: dict
    ):
        self.cursor = cursor
        self.encryption_manager = encryption_manager
        self.auto_encrypt = auto_encrypt
        self.encrypted_fields = encrypted_fields
        self._last_table = None

    def execute(self, sql: str, params: tuple | dict | None = None) -> "EncryptedCursor":
        """
        Ejecuta query cifrando automáticamente valores si es INSERT/UPDATE.

        Args:
            sql: SQL query
            params: Parámetros

        Returns:
            self (para encadenamiento)
        """
        if self.auto_encrypt:
            # Detectar tabla y operación
            sql_upper = sql.upper()
            self._last_table = self._extract_table_name(sql)

            # Cifrar parámetros para INSERT/UPDATE
            if self._last_table and ("INSERT" in sql_upper or "UPDATE" in sql_upper):
                params = self._encrypt_params(self._last_table, params)

        self.cursor.execute(sql, params or ())
        return self

    def executemany(self, sql: str, params: List) -> "EncryptedCursor":
        """
        Ejecuta múltiples queries.

        Args:
            sql: SQL query
            params: Lista de parámetros

        Returns:
            self
        """
        if self.auto_encrypt:
            sql_upper = sql.upper()
            self._last_table = self._extract_table_name(sql)

            if self._last_table and ("INSERT" in sql_upper or "UPDATE" in sql_upper):
                params = [self._encrypt_params(self._last_table, p) for p in params]

        self.cursor.executemany(sql, params)
        return self

    def fetchone(self) -> dict | None:
        """Obtiene una fila y descifra campos sensibles."""
        row = self.cursor.fetchone()
        if row and self.auto_encrypt and self._last_table:
            row = self._decrypt_row(dict(row), self._last_table)
        return row

    def fetchall(self) -> List[dict]:
        """Obtiene todas las filas y descifra campos sensibles."""
        rows = self.cursor.fetchall()
        if self.auto_encrypt and self._last_table and rows:
            rows = [self._decrypt_row(dict(row), self._last_table) for row in rows]
        return rows

    def fetchmany(self, size: int) -> List[dict]:
        """Obtiene múltiples filas."""
        rows = self.cursor.fetchmany(size)
        if self.auto_encrypt and self._last_table and rows:
            rows = [self._decrypt_row(dict(row), self._last_table) for row in rows]
        return rows

    @property
    def rowcount(self):
        return self.cursor.rowcount

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    @property
    def description(self):
        return self.cursor.description

    def close(self):
        self.cursor.close()

    # Métodos privados

    @staticmethod
    def _extract_table_name(sql: str) -> str | None:
        """Extrae nombre de tabla de SQL query."""
        sql_upper = sql.upper()
        for keyword in ["FROM", "INTO", "UPDATE"]:
            idx = sql_upper.find(keyword)
            if idx != -1:
                rest = sql[idx + len(keyword):].strip()
                table_name = rest.split()[0].split("(")[0].strip("`\"")
                return table_name
        return None

    def _encrypt_params(
        self,
        table: str,
        params: tuple | dict | None
    ) -> tuple | dict | None:
        """Cifra parámetros que correspondan a campos sensibles."""
        if not params:
            return params

        encrypted_cols = self.encrypted_fields.get(table, [])
        if not encrypted_cols:
            return params

        if isinstance(params, dict):
            result = params.copy()
            for col in encrypted_cols:
                if col in result and result[col]:
                    result[col] = self.encryption_manager.encrypt(str(result[col]))
            return result
        elif isinstance(params, (tuple, list)):
            # Para tuplas, es más complejo: no sabemos qué posición corresponde a qué
            # Por eso es mejor usar dict parameters con nombres
            return params
        return params

    def _decrypt_row(self, row: dict, table: str) -> dict:
        """Descifra campos sensibles en una fila."""
        encrypted_cols = self.encrypted_fields.get(table, [])
        for col in encrypted_cols:
            if col in row and row[col]:
                try:
                    row[col] = self.encryption_manager.decrypt(row[col])
                except Exception:
                    # Si falla descifrado, dejar como está (datos corruptos)
                    pass
        return row
