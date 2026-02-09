"""Fraud Intelligence Aggregator - Truecaller-style merchant reputation."""

import json
import logging
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional, List

from caps.intelligence.models import (
    MerchantReport,
    ReportType,
    MerchantScore,
    MerchantBadge,
)


logger = logging.getLogger(__name__)


class FraudIntelligence:
    """
    Crowdsourced Fraud Intelligence System.
    
    Like Truecaller for payments:
    - Users can report merchants as scam/legitimate
    - Aggregates reports into community scores
    - Assigns badges based on report patterns
    - Integrates with Policy Engine for decisions
    
    Badge Assignment:
    - VERIFIED_SAFE: 100+ reports, <1% scam rate
    - LIKELY_SAFE: 20+ reports, <5% scam rate
    - UNKNOWN: Insufficient data
    - CAUTION: 5-20% scam rate
    - LIKELY_SCAM: >20% scam rate
    - CONFIRMED_SCAM: Admin-verified scam
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize fraud intelligence.
        
        Args:
            db_path: Path to SQLite database. If None, uses in-memory DB.
        """
        self.db_path = db_path or ":memory:"
        
        # Keep persistent connection for in-memory DBs
        self._conn: Optional[sqlite3.Connection] = None
        if self.db_path == ":memory:":
            self._conn = sqlite3.connect(":memory:")
        
        self._init_db()
        
        logger.info(f"Fraud Intelligence initialized: {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        if self._conn:
            return self._conn
        return sqlite3.connect(self.db_path)
    
    def _close_connection(self, conn: sqlite3.Connection) -> None:
        """Close connection if not persistent."""
        if conn != self._conn:
            conn.close()
    
    def report_merchant(
        self,
        merchant_vpa: str,
        reporter_id: str,
        report_type: ReportType,
        reason: Optional[str] = None,
        transaction_id: Optional[str] = None,
        transaction_hash: Optional[str] = None,
    ) -> MerchantReport:
        """
        Submit a report about a merchant.
        
        Args:
            merchant_vpa: Merchant to report
            reporter_id: User submitting report
            report_type: Type of report
            reason: Optional text reason
            transaction_id: Link to transaction
            transaction_hash: Hash for verification
            
        Returns:
            Created MerchantReport
        """
        report = MerchantReport(
            merchant_vpa=merchant_vpa,
            reporter_id=reporter_id,
            report_type=report_type,
            reason=reason,
            transaction_id=transaction_id,
            transaction_hash=transaction_hash,
        )
        
        # Store report
        self._store_report(report)
        
        # Update aggregated score
        self._update_score(merchant_vpa)
        
        logger.info(
            f"Report submitted: {merchant_vpa} [{report_type.value}] by {reporter_id}"
        )
        
        return report
    
    def get_merchant_score(self, merchant_vpa: str) -> MerchantScore:
        """
        Get aggregated score for a merchant.
        
        Returns score with badge. If no reports exist,
        returns UNKNOWN badge with neutral score.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM scores WHERE merchant_vpa = ?",
            (merchant_vpa,)
        )
        row = cursor.fetchone()
        self._close_connection(conn)
        
        if row:
            return self._row_to_score(row)
        
        # No reports - return unknown
        return MerchantScore(
            merchant_vpa=merchant_vpa,
            badge=MerchantBadge.UNKNOWN,
        )
    
    def get_reports_for_merchant(
        self,
        merchant_vpa: str,
        limit: int = 20,
    ) -> List[MerchantReport]:
        """Get recent reports for a merchant."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """SELECT * FROM reports 
               WHERE merchant_vpa = ? 
               ORDER BY timestamp DESC 
               LIMIT ?""",
            (merchant_vpa, limit)
        )
        rows = cursor.fetchall()
        self._close_connection(conn)
        
        return [self._row_to_report(row) for row in rows]
    
    def get_scam_merchants(self, limit: int = 20) -> List[MerchantScore]:
        """Get merchants with highest scam rates."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """SELECT * FROM scores 
               WHERE badge IN ('LIKELY_SCAM', 'CONFIRMED_SCAM')
               ORDER BY scam_rate DESC 
               LIMIT ?""",
            (limit,)
        )
        rows = cursor.fetchall()
        self._close_connection(conn)
        
        return [self._row_to_score(row) for row in rows]
    
    def verify_merchant_as_scam(
        self,
        merchant_vpa: str,
        admin_id: str,
    ) -> None:
        """Admin action: Mark merchant as confirmed scam."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """UPDATE scores 
               SET badge = ?, last_updated = ?
               WHERE merchant_vpa = ?""",
            (MerchantBadge.CONFIRMED_SCAM.value, datetime.now(UTC).isoformat(), merchant_vpa)
        )
        
        conn.commit()
        self._close_connection(conn)
        
        logger.warning(f"Merchant {merchant_vpa} marked as CONFIRMED_SCAM by {admin_id}")
    
    def verify_merchant_as_safe(
        self,
        merchant_vpa: str,
        admin_id: str,
    ) -> None:
        """Admin action: Mark merchant as verified safe."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """UPDATE scores 
               SET badge = ?, last_updated = ?
               WHERE merchant_vpa = ?""",
            (MerchantBadge.VERIFIED_SAFE.value, datetime.now(UTC).isoformat(), merchant_vpa)
        )
        
        conn.commit()
        self._close_connection(conn)
        
        logger.info(f"Merchant {merchant_vpa} marked as VERIFIED_SAFE by {admin_id}")
    
    def _update_score(self, merchant_vpa: str) -> None:
        """Update aggregated score for a merchant."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Count reports by type
        cursor.execute(
            """SELECT report_type, COUNT(*) 
               FROM reports 
               WHERE merchant_vpa = ? 
               GROUP BY report_type""",
            (merchant_vpa,)
        )
        counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        scam = counts.get(ReportType.SCAM.value, 0)
        suspicious = counts.get(ReportType.SUSPICIOUS.value, 0)
        legitimate = counts.get(ReportType.LEGITIMATE.value, 0)
        verified = counts.get(ReportType.VERIFIED.value, 0)
        
        total = scam + suspicious + legitimate + verified
        
        # Calculate scam rate
        negative = scam + (suspicious * 0.5)  # Suspicious counts as half
        scam_rate = negative / total if total > 0 else 0.0
        
        # Calculate community score (0 = scam, 1 = safe)
        community_score = 1.0 - scam_rate
        
        # Determine badge
        badge = self._calculate_badge(total, scam_rate, scam)
        
        # Get first/last report times
        cursor.execute(
            """SELECT MIN(timestamp), MAX(timestamp) 
               FROM reports 
               WHERE merchant_vpa = ?""",
            (merchant_vpa,)
        )
        times = cursor.fetchone()
        
        # Upsert score
        cursor.execute(
            """INSERT INTO scores 
               (merchant_vpa, total_reports, scam_reports, suspicious_reports,
                legitimate_reports, verified_reports, community_score, scam_rate,
                badge, first_report, last_report, last_updated)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(merchant_vpa) DO UPDATE SET
                total_reports = ?,
                scam_reports = ?,
                suspicious_reports = ?,
                legitimate_reports = ?,
                verified_reports = ?,
                community_score = ?,
                scam_rate = ?,
                badge = ?,
                last_report = ?,
                last_updated = ?""",
            (
                # Insert values
                merchant_vpa, total, scam, suspicious, legitimate, verified,
                community_score, scam_rate, badge.value, times[0], times[1],
                datetime.now(UTC).isoformat(),
                # Update values
                total, scam, suspicious, legitimate, verified,
                community_score, scam_rate, badge.value, times[1],
                datetime.now(UTC).isoformat(),
            )
        )
        
        conn.commit()
        self._close_connection(conn)
    
    def _calculate_badge(
        self,
        total_reports: int,
        scam_rate: float,
        confirmed_scams: int,
    ) -> MerchantBadge:
        """Calculate badge based on report patterns."""
        if total_reports < 5:
            return MerchantBadge.UNKNOWN
        
        if scam_rate > 0.20:
            return MerchantBadge.LIKELY_SCAM
        elif scam_rate > 0.05:
            return MerchantBadge.CAUTION
        elif total_reports >= 100 and scam_rate < 0.01:
            return MerchantBadge.VERIFIED_SAFE
        elif total_reports >= 20 and scam_rate < 0.05:
            return MerchantBadge.LIKELY_SAFE
        else:
            return MerchantBadge.UNKNOWN
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Reports table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                merchant_vpa TEXT NOT NULL,
                reporter_id TEXT NOT NULL,
                report_type TEXT NOT NULL,
                reason TEXT,
                transaction_id TEXT,
                transaction_hash TEXT,
                timestamp TEXT NOT NULL,
                verified INTEGER DEFAULT 0,
                verified_by TEXT
            )
        """)
        
        # Scores table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scores (
                merchant_vpa TEXT PRIMARY KEY,
                total_reports INTEGER DEFAULT 0,
                scam_reports INTEGER DEFAULT 0,
                suspicious_reports INTEGER DEFAULT 0,
                legitimate_reports INTEGER DEFAULT 0,
                verified_reports INTEGER DEFAULT 0,
                community_score REAL DEFAULT 0.5,
                scam_rate REAL DEFAULT 0.0,
                badge TEXT DEFAULT 'UNKNOWN',
                first_report TEXT,
                last_report TEXT,
                last_updated TEXT
            )
        """)
        
        # Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_reports_merchant ON reports(merchant_vpa)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scores_badge ON scores(badge)"
        )
        
        conn.commit()
        self._close_connection(conn)
    
    def _store_report(self, report: MerchantReport) -> None:
        """Store report in database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO reports 
               (report_id, merchant_vpa, reporter_id, report_type, reason,
                transaction_id, transaction_hash, timestamp, verified, verified_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report.report_id,
                report.merchant_vpa,
                report.reporter_id,
                report.report_type.value,
                report.reason,
                report.transaction_id,
                report.transaction_hash,
                report.timestamp.isoformat(),
                1 if report.verified else 0,
                report.verified_by,
            )
        )
        
        conn.commit()
        self._close_connection(conn)
    
    def _row_to_report(self, row: tuple) -> MerchantReport:
        """Convert database row to MerchantReport."""
        return MerchantReport(
            report_id=row[0],
            merchant_vpa=row[1],
            reporter_id=row[2],
            report_type=ReportType(row[3]),
            reason=row[4],
            transaction_id=row[5],
            transaction_hash=row[6],
            timestamp=datetime.fromisoformat(row[7]),
            verified=bool(row[8]),
            verified_by=row[9],
        )
    
    def _row_to_score(self, row: tuple) -> MerchantScore:
        """Convert database row to MerchantScore."""
        return MerchantScore(
            merchant_vpa=row[0],
            total_reports=row[1],
            scam_reports=row[2],
            suspicious_reports=row[3],
            legitimate_reports=row[4],
            verified_reports=row[5],
            community_score=row[6],
            scam_rate=row[7],
            badge=MerchantBadge(row[8]),
            first_report=datetime.fromisoformat(row[9]) if row[9] else None,
            last_report=datetime.fromisoformat(row[10]) if row[10] else None,
            last_updated=datetime.fromisoformat(row[11]) if row[11] else datetime.now(UTC),
        )
    
    def close(self) -> None:
        """Close persistent connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
