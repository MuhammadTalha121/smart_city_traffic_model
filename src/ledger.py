"""
Tamper-evident violation audit ledger .
Hash-chained CSV storage with SHA256 integrity verification.
"""

import csv
import hashlib
import json
import os
from typing import Any, Dict, Optional

from src.config import (
    HASH_ALGORITHM,
    LEDGER_GENESIS_HASH,
    VIOLATION_LEDGER_PATH,
)


class ViolationLedger:
    """Hash-chained ledger for traffic violations."""

    def __init__(
        self,
        path: str = VIOLATION_LEDGER_PATH,
        genesis_hash: str = LEDGER_GENESIS_HASH,
        algorithm: str = HASH_ALGORITHM,
    ):
        self.path = path
        self.genesis_hash = genesis_hash
        self.algorithm = algorithm
        self._ensure_csv()

    def _ensure_csv(self) -> None:
        """Create CSV with headers if missing."""
        if not os.path.exists(self.path):
            with open(self.path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'block_number',
                    'previous_hash',
                    'block_hash',
                    'vehicle_id_hash',
                    'violation_type',
                    'zone',
                    'timestamp',
                    'penalty_sar',
                ])

    def _compute_block_hash(self, block_data: Dict[str, Any], previous_hash: str) -> str:
        """
        Compute SHA256 of canonical JSON block_data + previous_hash.
        The JSON is sorted and compact (no spaces).
        """
        json_str = json.dumps(block_data, sort_keys=True, separators=(',', ':'))
        combined = json_str + previous_hash
        return hashlib.sha256(combined.encode('utf-8')).hexdigest()

    def append_violation(
        self,
        vehicle_id_hash: str,
        violation_type: str,
        zone: str,
        timestamp: str,
        penalty_sar: float,
    ) -> Dict[str, Any]:
        """
        Append a new violation record, hash it, and return the full row.
        The previous hash is taken from the last stored block (or genesis).
        """
        # Read last row to get previous hash
        last_hash = self.genesis_hash
        block_number = 1
        if os.path.exists(self.path) and os.path.getsize(self.path) > 0:
            with open(self.path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    last_row = rows[-1]
                    last_hash = last_row['block_hash']
                    block_number = int(last_row['block_number']) + 1

        # Prepare block data (excludes previous_hash and block_hash)
        block_data = {
            'vehicle_id_hash': vehicle_id_hash,
            'violation_type': violation_type,
            'zone': zone,
            'timestamp': timestamp,
            'penalty_sar': penalty_sar,
        }

        block_hash = self._compute_block_hash(block_data, last_hash)

        # Build the CSV row
        row = {
            'block_number': block_number,
            'previous_hash': last_hash,
            'block_hash': block_hash,
            **block_data,
        }

        # Append to CSV
        with open(self.path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())
            writer.writerow(row)

        return row

    def verify_chain(self) -> Dict[str, Any]:
        """
        Verify the entire chain by recomputing each hash.
        Returns:
            - valid: bool
            - total_blocks: int
            - first_invalid_block: int | None (1-indexed block number)
        """
        if not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            return {'valid': True, 'total_blocks': 0, 'first_invalid_block': None}

        with open(self.path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        total_blocks = len(rows)
        prev_hash = self.genesis_hash

        for idx, row in enumerate(rows, start=1):
            # The previous hash stored in the row must match the hash of the previous block
            if row['previous_hash'] != prev_hash:
                return {
                    'valid': False,
                    'total_blocks': total_blocks,
                    'first_invalid_block': idx,
                }

            # Reconstruct block_data (exclude previous_hash and block_hash)
            block_data = {
                'vehicle_id_hash': row['vehicle_id_hash'],
                'violation_type': row['violation_type'],
                'zone': row['zone'],
                'timestamp': row['timestamp'],
                'penalty_sar': float(row['penalty_sar']),
            }

            expected_hash = self._compute_block_hash(block_data, row['previous_hash'])
            if expected_hash != row['block_hash']:
                return {
                    'valid': False,
                    'total_blocks': total_blocks,
                    'first_invalid_block': idx,
                }

            prev_hash = row['block_hash']

        return {'valid': True, 'total_blocks': total_blocks, 'first_invalid_block': None}