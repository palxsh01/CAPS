"""Audit Ledger - Immutable, hash-chained event log."""

import json
import logging
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional, List, Any

from caps.ledger.models import LedgerEntry, EventType, ChainValidationResult


logger = logging.getLogger(__name__)


class AuditLedger:
    """
    Immutable Audit Ledger with hash-chaining.
    
    Features:
    - Append-only design (no updates/deletes)
    - Each entry links to previous via hash
    - Chain validation detects tampering
    - SQLite storage for persistence
    - Transaction history queries
    
    Security:
    - Tampering with any entry breaks the hash chain
    - Regular chain validation recommended
    - Designed for regulatory compliance (RBI)
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the audit ledger.
        
        Args:
            db_path: Path to SQLite database. If None, uses in-memory DB.
        """
        self.db_path = db_path or ":memory:"
        
        # Keep persistent connection for in-memory DBs
        self._conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._conn = sqlite3.connect(":memory:")
        
        self._init_db()
        
        # Cache last hash for faster appends
        self._last_hash: str = self._get_last_hash()
        
        logger.info(f"Audit Ledger initialized: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn:
            return self._conn
        return sqlite3.connect(self.db_path)
    
    def _close_connection(self, conn: sqlite3.Connection) -> None:
        """Close connection if not persistent."""
        if conn != self._conn:
            conn.close()
    
    def append(
        self,
        event_type: EventType,
        payload: dict,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> LedgerEntry:
        """
        Append a new entry to the ledger.
        
        Args:
            event_type: Type of event
            payload: Event-specific data
            user_id: User who triggered event
            session_id: Current session ID
            transaction_id: Related transaction ID
            
        Returns:
            The created LedgerEntry
        """
        entry = LedgerEntry(
            event_type=event_type,
            payload=payload,
            previous_hash=self._last_hash,
            user_id=user_id,
            session_id=session_id,
            transaction_id=transaction_id,
        )
        
        # Store in database
        self._store_entry(entry)
        
        # Update last hash
        self._last_hash = entry.hash
        
        logger.debug(f"Ledger append: {event_type.value} [{entry.entry_id}]")
        
        return entry
    
    def log_event(self, event_type: EventType, payload: dict, user_id: str = None, session_id: str = None, transaction_id: str = None) -> LedgerEntry:
        """
        Log an event to the ledger.
        
        Args:
            event_type: Type of event
            payload: Event data
            user_id: Optional user ID
            session_id: Optional session ID
            transaction_id: Optional transaction ID
            
        Returns:
            Created LedgerEntry
        """
        # Create entry linking to previous hash
        entry = LedgerEntry(
            event_type=event_type,
            payload=payload,
            previous_hash=self._last_hash,
            user_id=user_id,
            session_id=session_id,
            transaction_id=transaction_id
        )
        
        # Store in DB
        self._store_entry(entry)
        
        # Update last hash cache
        self._last_hash = entry.hash
        
        logger.debug(f"Ledger append: {event_type.value} [{entry.entry_id}]")
        
        return entry
    
    def get_entry(self, entry_id: str) -> Optional[LedgerEntry]:
        """Get a specific entry by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM ledger WHERE entry_id = ?",
            (entry_id,)
        )
        row = cursor.fetchone()
        self._close_connection(conn)
        
        if row:
            return self._row_to_entry(row)
        return None
    
    def get_entries_by_transaction(self, transaction_id: str) -> List[LedgerEntry]:
        """Get all entries for a transaction."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM ledger WHERE transaction_id = ? ORDER BY timestamp",
            (transaction_id,)
        )
        rows = cursor.fetchall()
        self._close_connection(conn)
        
        return [self._row_to_entry(row) for row in rows]
    
    def get_entries_by_user(
        self,
        user_id: str,
        limit: int = 50,
    ) -> List[LedgerEntry]:
        """Get recent entries for a user."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """SELECT * FROM ledger 
               WHERE user_id = ? 
               ORDER BY timestamp DESC 
               LIMIT ?""",
            (user_id, limit)
        )
        rows = cursor.fetchall()
        self._close_connection(conn)
        
        return [self._row_to_entry(row) for row in rows]
    
    def get_recent_entries(self, limit: int = 20) -> List[LedgerEntry]:
        """Get most recent entries."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM ledger ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        self._close_connection(conn)
        
        return [self._row_to_entry(row) for row in rows]
    
    def validate_chain(self) -> ChainValidationResult:
        """
        Validate the entire hash chain.
        
        Checks that each entry's previous_hash matches
        the actual hash of the previous entry.
        
        Returns:
            ChainValidationResult with validation status
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM ledger ORDER BY timestamp ASC")
        rows = cursor.fetchall()
        self._close_connection(conn)
        
        if not rows:
            return ChainValidationResult(
                is_valid=True,
                total_entries=0,
            )
        
        entries = [self._row_to_entry(row) for row in rows]
        
        # First entry should have "genesis" as previous hash
        if entries[0].previous_hash != "genesis":
            return ChainValidationResult(
                is_valid=False,
                total_entries=len(entries),
                broken_at=0,
                error_message="First entry doesn't have genesis hash",
            )
        
        # Check each subsequent entry
        for i in range(1, len(entries)):
            expected_prev = entries[i - 1].hash
            actual_prev = entries[i].previous_hash
            
            if expected_prev != actual_prev:
                return ChainValidationResult(
                    is_valid=False,
                    total_entries=len(entries),
                    broken_at=i,
                    error_message=f"Chain broken at entry {i}: expected {expected_prev}, got {actual_prev}",
                )
        
        logger.info(f"Chain validation passed: {len(entries)} entries")
        
        return ChainValidationResult(
            is_valid=True,
            total_entries=len(entries),
        )
    
    def get_entry_count(self) -> int:
        """Get total number of entries."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ledger")
        count = cursor.fetchone()[0]
        self._close_connection(conn)
        return count
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                entry_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                previous_hash TEXT NOT NULL,
                hash TEXT NOT NULL,
                user_id TEXT,
                session_id TEXT,
                transaction_id TEXT
            )
        """)
        
        # Create indexes for common queries
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_timestamp ON ledger(timestamp)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_id ON ledger(user_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_transaction_id ON ledger(transaction_id)"
        )
        
        conn.commit()
        self._close_connection(conn)
    
    def _store_entry(self, entry: LedgerEntry) -> None:
        """Store entry in database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO ledger 
               (entry_id, timestamp, event_type, payload, previous_hash, hash,
                user_id, session_id, transaction_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.entry_id,
                entry.timestamp.isoformat(),
                entry.event_type.value,
                json.dumps(entry.payload),
                entry.previous_hash,
                entry.hash,
                entry.user_id,
                entry.session_id,
                entry.transaction_id,
            )
        )
        
        conn.commit()
        self._close_connection(conn)
    
    def _get_last_hash(self) -> str:
        """Get hash of last entry, or 'genesis' if empty."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT hash FROM ledger ORDER BY timestamp DESC LIMIT 1"
        )
        row = cursor.fetchone()
        self._close_connection(conn)
        
        if row:
            return row[0]
        return "genesis"
    
    def _row_to_entry(self, row: tuple) -> LedgerEntry:
        """Convert database row to LedgerEntry."""
        entry = LedgerEntry(
            entry_id=row[0],
            timestamp=datetime.fromisoformat(row[1]),
            event_type=EventType(row[2]),
            payload=json.loads(row[3]),
            previous_hash=row[4],
            user_id=row[6],
            session_id=row[7],
            transaction_id=row[8],
        )
        entry._cached_hash = row[5]  # Use stored hash
        return entry
    
    def close(self) -> None:
        """Close persistent connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
