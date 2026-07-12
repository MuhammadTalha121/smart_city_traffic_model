"""
Tamper-evident violation audit ledger.
Hash-chained CSV storage with SHA256 integrity verification.

Hashing scheme (confirmed against the existing implementation before this
module was extended for PROMPT 068 — no change to the scheme itself):

    block_hash = SHA256( canonical_json(block_data) + previous_hash )

where canonical_json = json.dumps(block_data, sort_keys=True,
separators=(',', ':')), and block_data is {vehicle_id_hash, violation_type,
zone, timestamp, penalty_sar} — it excludes block_number, previous_hash,
and block_hash itself. Each row's stored previous_hash must equal the
prior row's block_hash, chained back to LEDGER_GENESIS_HASH for block 1.
verify_chain() and verify_ledger_chain() both check exactly this, via a
single shared implementation (_verify_chain_rows) so there is only one
place the hashing logic can drift.

-----------------------------------------------------------------------
BREAK-RECOVERY PROCEDURE (PROMPT 068)
-----------------------------------------------------------------------
If verify_ledger_chain() (or the equivalent ViolationLedger.verify_chain())
reports valid=False:

1. FREEZE - append_violation() re-verifies the chain before every write
   (when LEDGER_FREEZE_ON_BREAK is True in config.py, the default) and
   raises LedgerIntegrityError instead of appending onto an already-broken
   chain. This is enforced in code, not just documented policy: a citation
   appended on top of a tampered chain would itself become unverifiable.

2. ALERT - the caller must surface the failure. app.py registers a FastAPI
   exception handler for LedgerIntegrityError that returns HTTP 503 with
   the same report shape (valid, total_rows, first_break_at_row), so a
   frozen ledger is visible in the API response rather than presenting as
   a generic 500 or, worse, a silently-dropped citation.

3. INVESTIGATE - first_break_at_row tells an investigator exactly which
   row to start with: either that row's previous_hash doesn't match the
   prior row's stored block_hash, or its own block_hash doesn't match what
   recomputing from its block_data + previous_hash produces. Compare
   against any off-system backup of the ledger CSV (nightly file backup,
   or source-control history if the file happens to be tracked) to judge
   whether the break is accidental corruption or deliberate tampering.

4. RECOVERY - there is no automated repair, by design. A human must either
   restore the ledger file from a known-good backup taken before the break,
   or, absent a backup, deliberately decide to truncate at the last valid
   block and accept the loss of every citation issued after that point
   (re-collecting them from source systems if possible). Recovery is
   always a logged, human decision - never automatic.

KNOWN LIMITATION: a single corrupted or tampered row freezes ALL future
citations system-wide, including ones unrelated to the broken row. This is
a deliberate fail-closed choice (appending onto a possibly-tampered chain
is worse than refusing to append), but it is also a denial-of-service risk
if the break is accidental (e.g. a bad disk write) rather than malicious.
That tradeoff is intentional and stated here rather than left implicit.
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
    LEDGER_FREEZE_ON_BREAK,
)


class LedgerIntegrityError(RuntimeError):
    """
    Raised by ViolationLedger.append_violation() when the existing chain
    is found to be broken before a new write would be appended onto it.

    Carries the same report shape as verify_ledger_chain() (.report) so a
    caller - e.g. the FastAPI exception handler in app.py - can surface
    first_break_at_row directly without re-running verification.
    """

    def __init__(self, report: Dict[str, Any]):
        self.report = report
        super().__init__(
            f"Ledger chain is broken at row {report.get('first_break_at_row')} "
            f"- refusing to append a new violation onto a compromised chain."
        )


def _verify_chain_rows(
    path: str,
    genesis_hash: str,
    algorithm: str = 'sha256',
) -> Dict[str, Any]:
    """
    Shared verification walk used by both ViolationLedger.verify_chain()
    (legacy key names: total_blocks / first_invalid_block, kept for
    backward compatibility with existing callers such as
    /citations/verify-ledger and the original PROMPT 049 tests) and the
    module-level verify_ledger_chain() added in PROMPT 068 (total_rows /
    first_break_at_row). Recomputes each row's hash from its block_data
    and the prior row's stored block_hash, comparing against the row's
    own stored block_hash.

    Returns
    -------
    dict with valid (bool), total_rows (int),
    first_break_at_row (int | None, 1-indexed).
    """
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return {'valid': True, 'total_rows': 0, 'first_break_at_row': None}

    with open(path, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total_rows = len(rows)
    prev_hash = genesis_hash

    for idx, row in enumerate(rows, start=1):
        if row['previous_hash'] != prev_hash:
            return {'valid': False, 'total_rows': total_rows, 'first_break_at_row': idx}

        block_data = {
            'vehicle_id_hash': row['vehicle_id_hash'],
            'violation_type': row['violation_type'],
            'zone': row['zone'],
            'timestamp': row['timestamp'],
            'penalty_sar': float(row['penalty_sar']),
        }
        json_str = json.dumps(block_data, sort_keys=True, separators=(',', ':'))
        expected_hash = hashlib.new(
            algorithm, (json_str + row['previous_hash']).encode('utf-8')
        ).hexdigest()

        if expected_hash != row['block_hash']:
            return {'valid': False, 'total_rows': total_rows, 'first_break_at_row': idx}

        prev_hash = row['block_hash']

    return {'valid': True, 'total_rows': total_rows, 'first_break_at_row': None}


def verify_ledger_chain(
    ledger_path: str = VIOLATION_LEDGER_PATH,
    genesis_hash: str = LEDGER_GENESIS_HASH,
    algorithm: str = HASH_ALGORITHM,
) -> Dict[str, Any]:
    """
    - module-level, on-demand chain verification.

    Same hash-chaining logic as ViolationLedger.verify_chain(), exposed as
    a standalone function so it can be called without instantiating a
    ViolationLedger (used by GET /ledger/verify and by the pre-write
    freeze check in append_violation()). Result key names match the
    PROMPT 068 spec exactly: valid, total_rows, first_break_at_row - this
    intentionally differs from verify_chain()'s legacy
    total_blocks/first_invalid_block names, which are kept unchanged on
    the instance method for backward compatibility. Both call the same
    underlying _verify_chain_rows(), so there is exactly one hashing
    implementation to keep correct.

    Returns
    -------
    dict with valid (bool), total_rows (int),
    first_break_at_row (int | None, 1-indexed).
    """
    return _verify_chain_rows(ledger_path, genesis_hash, algorithm)


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
    import portalocker
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

         when LEDGER_FREEZE_ON_BREAK is True (the default),
        this re-verifies the existing chain before writing and raises
        LedgerIntegrityError instead of appending onto an already-broken
        chain. See the module docstring's BREAK-RECOVERY PROCEDURE.
        """
        if LEDGER_FREEZE_ON_BREAK:
            pre_check = self.verify_chain()
            if not pre_check['valid']:
                raise LedgerIntegrityError({
                    'valid': False,
                    'total_rows': pre_check['total_blocks'],
                    'first_break_at_row': pre_check['first_invalid_block'],
                })

        # Acquire exclusive lock for the entire read+write operation
        with open(self.path, 'r+', newline='', encoding='utf-8') as f:
            portalocker.lock(f, portalocker.LOCK_EX)

            # Read last row to get previous hash and block number
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                last_row = rows[-1]
                last_hash = last_row['block_hash']
                block_number = int(last_row['block_number']) + 1
            else:
                last_hash = self.genesis_hash
                block_number = 1

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

            # Move cursor to the end of the file for appending
            f.seek(0, 2)

            # Write the new row
            writer = csv.DictWriter(f, fieldnames=row.keys())
            writer.writerow(row)

            portalocker.unlock(f)

        return row

    def verify_chain(self) -> Dict[str, Any]:
        """
        Verify the entire chain by recomputing each hash.

        Kept with its original key names (total_blocks, first_invalid_block)
        for backward compatibility with existing callers
        (/citations/verify-ledger, tests/test_model.py's PROMPT 049 ledger
        tests). Delegates to the same row-walk used by verify_ledger_chain()
        so there is exactly one hashing implementation in this module.

        Returns:
            - valid: bool
            - total_blocks: int
            - first_invalid_block: int | None (1-indexed block number)
        """
        result = _verify_chain_rows(self.path, self.genesis_hash, self.algorithm)
        return {
            'valid': result['valid'],
            'total_blocks': result['total_rows'],
            'first_invalid_block': result['first_break_at_row'],
        }
