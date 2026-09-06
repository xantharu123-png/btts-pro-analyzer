from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from threading import Barrier
import unittest
from unittest.mock import patch
import zipfile

from challenge_engine import (
    CHALLENGE_MODEL_CONTRACT_SIGNATURE,
    MARKET_BY_KEY,
    MARKET_SPECS,
    ChallengeCandidate,
    ValidationMetrics,
    select_quoted_ticket,
    ticket_stake,
)
from challenge_store import (
    FINANCIAL_CHAIN_VERSION,
    FINANCIAL_ZERO_HASH,
    LEDGER_CHECKPOINT_MIGRATION_ENV,
    LEDGER_HMAC_KEY_FILE_ENV,
    LEDGER_HMAC_REQUIRED_ENV,
    SETTLEMENT_CHAIN_VERSION,
    SETTLEMENT_ZERO_HASH,
    ChallengeLedger,
    TICKET_DEFINITION_VERSION,
    _challenge_schema_manifest,
    _challenge_sequence_state,
    _definition_hash_payload,
    _financial_record_mac,
    _legacy_financial_record_hash,
    _settlement_record_mac,
)
from market_consensus import parse_fixture_consensus
from price_ledger import (
    PriceLedger,
    PriceLedgerError,
    PriceQuote,
    _record_hash as _price_record_hash,
    _row_payload as _price_row_payload,
)
from scripts import backup_runtime_databases as backup


def _candidate(now: datetime, *, probability: float = 0.60) -> ChallengeCandidate:
    validation = ValidationMetrics(
        300,
        0.15,
        0.20,
        0.25,
        0.04,
        True,
        calibration_bins=4,
        min_bin_size=30,
        max_calibration_error=0.06,
        max_error_bin_size=30,
        max_error_bin_mean_probability=0.70,
        paired_loss_mean=0.05,
        paired_loss_hac_standard_error=0.005,
        paired_loss_lower_confidence_bound=0.0418,
        paired_loss_p_value=0.00001,
        fdr_q_value=0.0009,
        tested_hypotheses=len(MARKET_SPECS),
        statistical_release_passed=True,
    )
    item = ChallengeCandidate(
        candidate_id="1:BTTS",
        fixture_id=1,
        league_id=39,
        league_name="Integrity League",
        kickoff=(now + timedelta(days=1)).isoformat(),
        home_team_id=10,
        away_team_id=11,
        home_team="Integrity Home",
        away_team="Integrity Away",
        market_key="BTTS_YES",
        market="Beide Teams treffen",
        selection="Ja",
        probability=probability + 0.03,
        conservative_probability=probability,
        probability_haircut_pp=3.0,
        model_price=1.0 / probability,
        evidence_score=90.0,
        model_spread_pp=2.0,
        expected_home_goals=1.5,
        expected_away_goals=1.2,
        venue_samples=(10, 10),
        form_samples=(6, 6),
        validation=validation,
    )
    item.context = {
        "passed": True,
        "forecast_passed": True,
        "release_context_complete": True,
        "release_eligible": True,
        "blocked_reasons": [],
    }
    return item


def _model_ticket(
    now: datetime,
    *,
    observation_id: int | None = None,
):
    item = _candidate(now)
    observation_ids = (
        {item.candidate_id: observation_id}
        if observation_id is not None
        else None
    )
    ticket = select_quoted_ticket(
        [item],
        {item.candidate_id: 2.10},
        quote_observation_ids=observation_ids,
        now=now,
    )
    assert ticket is not None
    return item, ticket


def _place_model_ticket(ledger: ChallengeLedger, now: datetime):
    _item, ticket = _model_ticket(now)
    ticket_id = ledger.place_ticket(
        now.date().isoformat(),
        ticket,
        ticket_stake(ticket, 100.0),
        now.isoformat(),
    )
    return ticket_id, ticket


def _downgrade_financial_chain_to_precheckpoint_v1(
    connection: sqlite3.Connection,
) -> None:
    """Build a complete public-SHA v1 fixture representing a real predecessor."""

    connection.row_factory = sqlite3.Row
    connection.execute("DROP TRIGGER challenge_transactions_no_update")
    connection.execute("DROP TRIGGER challenge_financial_anchor_immutable")
    previous_hash = FINANCIAL_ZERO_HASH
    anchor_hash = None
    for row in connection.execute(
        "SELECT * FROM challenge_transactions ORDER BY id ASC"
    ).fetchall():
        digest = _legacy_financial_record_hash(
            created_at=str(row["created_at"]),
            kind=str(row["kind"]),
            amount_cents=int(row["amount_cents"]),
            balance_after_cents=int(row["balance_after_cents"]),
            ticket_id=(
                int(row["ticket_id"])
                if row["ticket_id"] is not None
                else None
            ),
            note=row["note"],
            previous_hash=previous_hash,
            chain_version=1,
        )
        connection.execute(
            """
            UPDATE challenge_transactions
            SET chain_version=1, previous_hash=?, record_hash=?
            WHERE id=?
            """,
            (previous_hash, digest, int(row["id"])),
        )
        if anchor_hash is None:
            anchor_hash = digest
        previous_hash = digest
    connection.execute(
        """
        UPDATE challenge_settings
        SET financial_chain_version=1, financial_anchor_hash=?
        WHERE id=1
        """,
        (anchor_hash,),
    )
    connection.execute("DROP TABLE challenge_integrity_checkpoint")


def _create_plain_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            "CREATE TABLE runtime_state (id INTEGER PRIMARY KEY, value TEXT)"
        )
        connection.commit()


def _write_complete_legacy_marker(
    root: Path,
    marker_path: Path,
    receipt_paths: list[str],
) -> None:
    records = []
    for relative in receipt_paths:
        with closing(sqlite3.connect(root / relative)) as connection:
            checkpoint = connection.execute(
                "SELECT record_mac FROM challenge_integrity_checkpoint WHERE id=1"
            ).fetchone()
        assert checkpoint is not None
        records.append(
            {
                "path": relative,
                "checkpoint_mac": str(checkpoint[0]),
                "source": "v0",
            }
        )
    payload = {
        "contract_version": 1,
        "status": "complete",
        "mode": "legacy-v0",
        "application_root": str(root),
        "previous_head": "1" * 40,
        "previous_writer_blob": sorted(backup.LEGACY_V0_WRITER_BLOBS)[0],
        "target_head": "2" * 40,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "migration_receipt": {
            "contract_version": 1,
            "mode": "legacy-v0",
            "database_count": len(records),
            "databases": records,
        },
    }
    marker_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _build_backup_fixture(base: Path) -> tuple[Path, Path, Path, Path]:
    root = base / "app"
    root.mkdir()
    challenge_path = root / "challenge_15k.db"
    ledger = ChallengeLedger(challenge_path)
    _create_plain_database(root / "runtime.db")
    marker_path = base / "migration-marker.json"
    _write_complete_legacy_marker(root, marker_path, ["challenge_15k.db"])
    return root, challenge_path, ledger._integrity_key_path, marker_path


def _reference_ticket(now: datetime):
    item = _candidate(now)
    payload = {
        "errors": [],
        "response": [
            {
                "fixture": {"id": item.fixture_id, "date": item.kickoff},
                "update": now.isoformat(),
                "bookmakers": [
                    {
                        "id": index,
                        "name": f"Book {index}",
                        "bets": [
                            {
                                "name": "Both Teams Score",
                                "values": [{"value": "Yes", "odd": odds}],
                            }
                        ],
                    }
                    for index, odds in enumerate(
                        ("2.05", "2.10", "2.15", "2.20"),
                        start=1,
                    )
                ],
            }
        ],
    }
    quote = parse_fixture_consensus(payload, [item], fetched_at=now)[
        item.candidate_id
    ]
    executable = quote.executable_point
    assert executable is not None
    ticket = select_quoted_ticket(
        [item],
        {item.candidate_id: executable.odds},
        quote_metadata_by_candidate={
            item.candidate_id: {
                "source": quote.source,
                "quoted_at": quote.quoted_at,
                "fetched_at": quote.fetched_at,
                "bookmaker_count": quote.bookmaker_count,
                "quote_low": executable.odds,
                "quote_high": quote.best_odds,
            }
        },
        now=now,
    )
    assert ticket is not None
    return item, quote, ticket


class ModelContractIntegrityTests(unittest.TestCase):
    def test_existing_v11_model_ticket_remains_readable_and_standalone_verifiable(self):
        """A prediction upgrade must not invalidate authenticated money history."""
        now = datetime.now(timezone.utc)
        legacy_contract = "challenge-engine:hac-fdr-executable-frechet-v11"
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            # Build the historical fixture with its literal original contract,
            # independently of whatever contract the current engine exports.
            with (
                patch("challenge_store.CHALLENGE_MODEL_CONTRACT_SIGNATURE", legacy_contract),
                patch("price_ledger.CHALLENGE_MODEL_CONTRACT_SIGNATURE", legacy_contract),
            ):
                ledger = ChallengeLedger(db_path)
                ticket_id, _ticket = _place_model_ticket(ledger, now)
            stored = ChallengeLedger(db_path).get_ticket(ticket_id)
            self.assertEqual(stored["entry_source"], "MODEL")
            self.assertEqual(stored["model_contract_signature"], legacy_contract)
            self.assertEqual(stored["status"], "PENDING")
            self.assertTrue(stored["ticket_definition_hash"])
            self.assertTrue(stored["quote_evidence_hash"])
            backup.verify_current_challenge_database(
                db_path,
                ledger._integrity_key_path.read_bytes(),
                ledger_scope=str(db_path.resolve()),
            )

    def test_model_ticket_and_price_observation_share_central_signature(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id, _ticket = _place_model_ticket(ledger, now)
            stored = ledger.get_ticket(ticket_id)
            observation_id = stored["legs"][0]["quote_observation_id"]
            observation = PriceLedger(db_path).get(observation_id)

        self.assertEqual(TICKET_DEFINITION_VERSION, 3)
        self.assertEqual(
            stored["model_contract_signature"],
            CHALLENGE_MODEL_CONTRACT_SIGNATURE,
        )
        self.assertEqual(
            observation.model_ref,
            CHALLENGE_MODEL_CONTRACT_SIGNATURE,
        )
        self.assertEqual(stored["definition_version"], 3)
        self.assertTrue(stored["ticket_definition_hash"])
        self.assertTrue(stored["quote_evidence_hash"])

    def test_stale_challenge_price_contract_is_rejected_at_append(self):
        now = datetime.now(timezone.utc)
        item = _candidate(now)
        quote = PriceQuote(
            sport="FOOTBALL",
            event_id=str(item.fixture_id),
            event_name=f"{item.home_team} vs {item.away_team}",
            scheduled_start=item.kickoff,
            market_key=item.market_key,
            market_name=item.market,
            selection_key=item.candidate_id,
            selection_name=item.selection,
            decimal_odds=2.10,
            captured_at=now,
            model_ref="challenge-engine:obsolete-v1",
        )
        with tempfile.TemporaryDirectory() as tmp:
            prices = PriceLedger(Path(tmp) / "challenge.db")
            with self.assertRaisesRegex(PriceLedgerError, "stale model contract"):
                prices.append(quote, now=now)

    def test_model_ticket_rejects_observation_from_another_model(self):
        now = datetime.now(timezone.utc)
        item = _candidate(now)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            observation = PriceLedger(db_path).append(
                PriceQuote(
                    sport="FOOTBALL",
                    event_id=str(item.fixture_id),
                    event_name=f"{item.home_team} vs {item.away_team}",
                    scheduled_start=item.kickoff,
                    market_key=item.market_key,
                    market_name=item.market,
                    selection_key=item.candidate_id,
                    selection_name=item.selection,
                    decimal_odds=2.10,
                    captured_at=now,
                    model_ref="other-model:v1",
                ),
                now=now,
            )
            # Existing observations must already be covered by the challenge
            # checkpoint; only observations appended inside place_ticket may
            # advance it afterward.
            ledger = ChallengeLedger(db_path)
            _item, ticket = _model_ticket(now, observation_id=observation.id)

            with self.assertRaisesRegex(ValueError, "append-only N1Bet observation"):
                ledger.place_ticket(
                    now.date().isoformat(),
                    ticket,
                    ticket_stake(ticket, 100.0),
                    now.isoformat(),
                )

    def test_n1_ticket_summary_cannot_disagree_with_raw_observation(self):
        now = datetime.now(timezone.utc)
        _item, ticket = _model_ticket(now)
        mismatches = {
            "quote_low": 9.99,
            "quote_high": 9.99,
            "bookmaker_count": 2,
            "quoted_at": (now - timedelta(seconds=2)).isoformat(),
            "fetched_at": (now - timedelta(seconds=2)).isoformat(),
        }
        for field, value in mismatches.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                leg = replace(ticket.legs[0], **{field: value})
                tampered = replace(ticket, legs=(leg,))
                ledger = ChallengeLedger(Path(tmp) / "challenge.db")
                with self.assertRaisesRegex(ValueError, "N1Bet quote summary"):
                    ledger.place_ticket(
                        now.date().isoformat(),
                        tampered,
                        ticket_stake(tampered, 100.0),
                        now.isoformat(),
                    )


class TicketDefinitionIntegrityTests(unittest.TestCase):
    def test_standalone_backup_market_catalog_matches_application_catalog(self):
        expected = {
            key: (
                spec.kind,
                spec.side,
                spec.threshold,
                spec.low,
                spec.high,
            )
            for key, spec in MARKET_BY_KEY.items()
        }

        self.assertEqual(backup.CHALLENGE_MARKET_DEFINITIONS, expected)

    def test_v3_definition_and_evidence_fields_are_database_immutable(self):
        protected_updates = (
            "stake_cents = stake_cents + 1",
            "ticket_definition_hash = NULL",
            "quote_evidence_hash = NULL",
            "model_contract_signature = NULL",
        )
        for update in protected_updates:
            with self.subTest(update=update), tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "challenge.db"
                ledger = ChallengeLedger(db_path)
                ticket_id, _ticket = _place_model_ticket(
                    ledger,
                    datetime.now(timezone.utc),
                )
                with closing(sqlite3.connect(db_path)) as connection:
                    with self.assertRaises(sqlite3.DatabaseError):
                        connection.execute(
                            f"UPDATE challenge_tickets SET {update} WHERE id=?",
                            (ticket_id,),
                        )

    def test_hash_binds_stake_even_if_database_trigger_is_removed(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id, _ticket = _place_model_ticket(ledger, now)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "DROP TRIGGER challenge_ticket_v3_definition_immutable"
                )
                connection.execute(
                    "UPDATE challenge_tickets SET stake_cents=stake_cents+1 WHERE id=?",
                    (ticket_id,),
                )
                connection.commit()

            with self.assertRaisesRegex(RuntimeError, "integrity"):
                ledger.get_ticket(ticket_id)

    def test_public_definition_hash_recomputation_cannot_bypass_checkpoint(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id, _ticket = _place_model_ticket(ledger, now)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute(
                    "SELECT * FROM challenge_tickets WHERE id=?",
                    (ticket_id,),
                ).fetchone()
                forged_analysis_date = (
                    datetime.fromisoformat(str(row["analysis_date"]))
                    + timedelta(days=7)
                ).date().isoformat()
                forged_hash = _definition_hash_payload(
                    analysis_date=forged_analysis_date,
                    legs_json=str(row["legs_json"]),
                    quote_evidence_json=str(row["quote_evidence_json"]),
                    reference_total_odds=float(row["total_odds"]),
                    played_total_odds=float(row["played_odds"]),
                    joint_probability=float(row["joint_probability"]),
                    expected_roi=float(row["expected_roi"]),
                    definition_version=int(row["definition_version"]),
                    stake_cents=int(row["stake_cents"]),
                    created_at=str(row["created_at"]),
                    quote_verified_at=str(row["quote_verified_at"]),
                    analysis_timezone=str(row["analysis_timezone"]),
                    entry_source=str(row["entry_source"]),
                    model_contract_signature=str(row["model_contract_signature"]),
                )
                connection.execute(
                    "DROP TRIGGER challenge_ticket_v3_definition_immutable"
                )
                connection.execute(
                    """
                    UPDATE challenge_tickets
                    SET analysis_date=?, ticket_definition_hash=?
                    WHERE id=?
                    """,
                    (forged_analysis_date, forged_hash, ticket_id),
                )
                connection.commit()

            with closing(ledger._connect()) as connection:
                # The public SHA definition remains internally self-consistent.
                ledger._require_ticket_definitions(connection)
                self.assertEqual(
                    ledger._verify_financial_rows(
                        connection,
                        require_checkpoint=False,
                    ),
                    (True, None),
                )
            self.assertFalse(ledger.verify_financial_ledger()[0])
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.get_ticket(ticket_id)

    def test_v3_null_hashes_fail_closed_without_trigger(self):
        tampered_fields = (
            ("ticket_definition_hash", "definition hash is required"),
            ("quote_evidence_hash", "model quote evidence is required"),
        )
        for field, message in tampered_fields:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "challenge.db"
                ledger = ChallengeLedger(db_path)
                ticket_id, _ticket = _place_model_ticket(
                    ledger,
                    datetime.now(timezone.utc),
                )
                with closing(sqlite3.connect(db_path)) as connection:
                    connection.execute(
                        "DROP TRIGGER challenge_ticket_v3_definition_immutable"
                    )
                    connection.execute(
                        f"UPDATE challenge_tickets SET {field}=NULL WHERE id=?",
                        (ticket_id,),
                    )
                    connection.commit()

                with self.assertRaisesRegex(RuntimeError, message):
                    ledger.get_ticket(ticket_id)

    def test_settlement_columns_remain_mutable_through_ledger(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ticket_id, _ticket = _place_model_ticket(ledger, now)
            settled = ledger.settle_ticket(ticket_id, "LOST")

            self.assertEqual(settled["status"], "LOST")
            self.assertEqual(ledger.verify_financial_ledger(), (True, None))

    def test_manual_v3_ticket_is_hashed_without_model_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            ticket_id = ledger.record_manual_result(
                (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat(),
                "Historischer Integritätstest",
                5.0,
                2.0,
                "LOST",
            )
            stored = ledger.get_ticket(ticket_id)

        self.assertEqual(stored["definition_version"], 3)
        self.assertEqual(stored["entry_source"], "MANUAL")
        self.assertIsNone(stored["model_contract_signature"])
        self.assertIsNone(stored["quote_evidence_hash"])
        self.assertTrue(stored["ticket_definition_hash"])


class ReferenceSummaryIntegrityTests(unittest.TestCase):
    def test_quoted_leg_summary_must_match_raw_reference_evidence(self):
        now = datetime.now(timezone.utc)
        item, quote, ticket = _reference_ticket(now)
        original_leg = ticket.legs[0]
        mismatches = {
            "quote_low": original_leg.quote_low + 0.01,
            "quote_high": original_leg.quote_high + 0.01,
            "quoted_at": (now - timedelta(seconds=1)).isoformat(),
            "fetched_at": (now - timedelta(seconds=1)).isoformat(),
            "bookmaker_count": original_leg.bookmaker_count + 1,
        }

        for field, value in mismatches.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                tampered_leg = replace(original_leg, **{field: value})
                tampered_ticket = replace(ticket, legs=(tampered_leg,))
                ledger = ChallengeLedger(Path(tmp) / "challenge.db")
                with self.assertRaisesRegex(
                    ValueError,
                    "summary|provider count|reference price evidence",
                ):
                    ledger.place_ticket(
                        now.date().isoformat(),
                        tampered_ticket,
                        ticket_stake(tampered_ticket, 100.0),
                        now.isoformat(),
                        reference_quote_evidence={
                            item.candidate_id: quote.to_dict()
                        },
                    )


class FinancialLedgerIntegrityTests(unittest.TestCase):
    def test_settings_tamper_blocks_reads_and_money_mutations(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET current_balance_cents=current_balance_cents+1
                    WHERE id=1
                    """
                )
                connection.commit()

            self.assertFalse(ledger.verify_financial_ledger()[0])
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.settings()
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.tickets()
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.set_balance(50.0)
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.set_stake_fraction(0.10)

    def test_checkpoint_authenticates_all_risk_and_target_settings(self):
        mutations = (
            "starting_balance_cents=starting_balance_cents+1",
            "target_balance_cents=target_balance_cents+1",
            "stake_fraction_bps=600",
            "stake_policy_version=999",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "challenge.db"
                ledger = ChallengeLedger(db_path)
                with closing(sqlite3.connect(db_path)) as connection:
                    connection.execute(
                        f"UPDATE challenge_settings SET {mutation} WHERE id=1"
                    )
                    connection.commit()

                # These fields do not participate in the running-balance
                # recurrence; only the authenticated current-state checkpoint
                # can make their coordinated rewrite fail closed.
                with closing(ledger._connect()) as connection:
                    self.assertEqual(
                        ledger._verify_financial_rows(
                            connection,
                            require_checkpoint=False,
                        ),
                        (True, None),
                    )
                self.assertFalse(ledger.verify_financial_ledger()[0])
                with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                    ledger.settings()

    def test_checkpoint_rejects_coordinated_financial_and_settlement_tail_truncation(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id, _ticket = _place_model_ticket(ledger, now)
            ledger.settle_ticket(ticket_id, "LOST")
            with closing(sqlite3.connect(db_path)) as connection:
                for trigger in (
                    "challenge_transactions_no_delete",
                    "challenge_settlement_events_no_delete",
                    "challenge_ticket_settlement_update_authorized",
                    "challenge_settlement_anchor_immutable",
                ):
                    connection.execute(f"DROP TRIGGER {trigger}")
                connection.execute(
                    "DELETE FROM challenge_transactions "
                    "WHERE id=(SELECT MAX(id) FROM challenge_transactions)"
                )
                connection.execute(
                    "DELETE FROM challenge_settlement_events "
                    "WHERE id=(SELECT MAX(id) FROM challenge_settlement_events)"
                )
                connection.execute(
                    """
                    UPDATE challenge_tickets
                    SET status='PENDING', payout_cents=0, settled_at=NULL,
                        settlement_odds=NULL, settlement_note=NULL
                    WHERE id=?
                    """,
                    (ticket_id,),
                )
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET settlement_anchor_hash=NULL
                    WHERE id=1
                    """
                )
                connection.commit()

            with closing(ledger._connect()) as connection:
                self.assertEqual(
                    ledger._verify_financial_rows(
                        connection,
                        require_checkpoint=False,
                    ),
                    (True, None),
                )
            self.assertFalse(ledger.verify_financial_ledger()[0])
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.transactions()

    def test_checkpoint_authenticates_legacy_ticket_materialized_state(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id, _ticket = _place_model_ticket(ledger, now)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute(
                    "SELECT * FROM challenge_tickets WHERE id=?",
                    (ticket_id,),
                ).fetchone()
                legacy_hash = _definition_hash_payload(
                    analysis_date=str(row["analysis_date"]),
                    legs_json=str(row["legs_json"]),
                    quote_evidence_json=str(row["quote_evidence_json"]),
                    reference_total_odds=float(row["total_odds"]),
                    played_total_odds=float(row["played_odds"]),
                    joint_probability=float(row["joint_probability"]),
                    expected_roi=float(row["expected_roi"]),
                    definition_version=0,
                )
                connection.execute(
                    "DROP TRIGGER challenge_ticket_v3_definition_immutable"
                )
                connection.execute(
                    "DROP TRIGGER challenge_ticket_settlement_update_authorized"
                )
                connection.execute(
                    """
                    UPDATE challenge_tickets
                    SET definition_version=0, entry_source='MANUAL',
                        model_contract_signature=NULL,
                        ticket_definition_hash=?, status='WON',
                        payout_cents=999999, settled_at=?,
                        settlement_odds=2.0,
                        settlement_note='forged legacy settlement'
                    WHERE id=?
                    """,
                    (legacy_hash, now.isoformat(), ticket_id),
                )
                connection.commit()

            with closing(ledger._connect()) as connection:
                ledger._require_ticket_definitions(connection)
                self.assertEqual(
                    ledger._verify_financial_rows(
                        connection,
                        require_checkpoint=False,
                    ),
                    (True, None),
                )
            self.assertFalse(ledger.verify_financial_ledger()[0])
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.get_ticket(ticket_id)

    def test_all_ticket_bound_transactions_require_an_existing_ticket(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            created_at = datetime.now(timezone.utc).isoformat()
            with closing(ledger._connect()) as connection:
                connection.execute("PRAGMA foreign_keys=OFF")
                connection.execute("BEGIN IMMEDIATE")
                tail = connection.execute(
                    "SELECT record_hash FROM challenge_transactions "
                    "ORDER BY id DESC LIMIT 1"
                ).fetchone()[0]
                balance = int(
                    connection.execute(
                        "SELECT current_balance_cents FROM challenge_settings WHERE id=1"
                    ).fetchone()[0]
                )
                forged_balance = balance - 1
                digest = _financial_record_mac(
                    ledger._integrity_key,
                    created_at=created_at,
                    kind="STAKE",
                    amount_cents=-1,
                    balance_after_cents=forged_balance,
                    ticket_id=999,
                    note="authenticated orphan transaction",
                    previous_hash=str(tail),
                )
                cursor = connection.execute(
                    """
                    INSERT INTO challenge_transactions (
                        created_at, kind, amount_cents, balance_after_cents,
                        ticket_id, note, chain_version, previous_hash, record_hash
                    ) VALUES (?, 'STAKE', -1, ?, 999, ?, ?, ?, ?)
                    """,
                    (
                        created_at,
                        forged_balance,
                        "authenticated orphan transaction",
                        FINANCIAL_CHAIN_VERSION,
                        tail,
                        digest,
                    ),
                )
                bad_id = int(cursor.lastrowid)
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET current_balance_cents=?, updated_at=? WHERE id=1
                    """,
                    (forged_balance, created_at),
                )
                # Sign the coordinated state to isolate the global FK invariant
                # from the checkpoint itself.
                ledger._refresh_integrity_checkpoint(connection)
                connection.commit()

            self.assertEqual(ledger.verify_financial_ledger(), (False, bad_id))
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.settings()

    def test_transaction_running_balance_tamper_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            with closing(sqlite3.connect(db_path)) as connection:
                with self.assertRaises(sqlite3.DatabaseError):
                    connection.execute(
                        """
                        INSERT INTO challenge_transactions (
                            created_at, kind, amount_cents,
                            balance_after_cents, note
                        ) VALUES (?, 'FORGED', 100, 10100, 'tamper')
                        """,
                        (datetime.now(timezone.utc).isoformat(),),
                    )

                # The UDF is intentionally treated only as defense in depth:
                # another sqlite writer can spoof it. A correctly linked public
                # SHA digest still cannot forge the external-key HMAC.
                connection.create_function(
                    "challenge_write_authorized",
                    0,
                    lambda: 1,
                    deterministic=True,
                )
                tail = connection.execute(
                    """
                    SELECT record_hash FROM challenge_transactions
                    ORDER BY id DESC LIMIT 1
                    """
                ).fetchone()[0]
                created_at = datetime.now(timezone.utc).isoformat()
                public_digest = _legacy_financial_record_hash(
                    created_at=created_at,
                    kind="BALANCE_ADJUSTMENT",
                    amount_cents=100,
                    balance_after_cents=10100,
                    ticket_id=None,
                    note="tamper",
                    previous_hash=tail,
                    chain_version=FINANCIAL_CHAIN_VERSION,
                )
                cursor = connection.execute(
                    """
                    INSERT INTO challenge_transactions (
                        created_at, kind, amount_cents, balance_after_cents, note,
                        chain_version, previous_hash, record_hash
                    ) VALUES (?, 'BALANCE_ADJUSTMENT', 100, 10100, 'tamper',
                              ?, ?, ?)
                    """,
                    (
                        created_at,
                        FINANCIAL_CHAIN_VERSION,
                        tail,
                        public_digest,
                    ),
                )
                bad_id = int(cursor.lastrowid)
                connection.execute(
                    "UPDATE challenge_settings SET current_balance_cents=10100 WHERE id=1"
                )
                connection.commit()

            self.assertEqual(ledger.verify_financial_ledger(), (False, bad_id))
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.transactions()
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.record_manual_result(
                    (datetime.now(timezone.utc) - timedelta(days=1))
                    .date()
                    .isoformat(),
                    "Blocked by forged ledger",
                    1.0,
                    2.0,
                    "LOST",
                )

    def test_materialized_settlement_tamper_is_blocked_and_reconciled(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id, _ticket = _place_model_ticket(ledger, now)
            with closing(sqlite3.connect(db_path)) as connection:
                with self.assertRaises(sqlite3.DatabaseError):
                    connection.execute(
                        """
                        UPDATE challenge_tickets
                        SET status='WON', payout_cents=999900, settled_at=?
                        WHERE id=?
                        """,
                        (datetime.now(timezone.utc).isoformat(), ticket_id),
                    )

                # Reconciliation remains a second fail-closed boundary even if
                # the database authorization trigger is deliberately removed.
                connection.execute(
                    "DROP TRIGGER challenge_ticket_settlement_update_authorized"
                )
                connection.execute(
                    """
                    UPDATE challenge_tickets
                    SET status='WON', payout_cents=999900, settled_at=?
                    WHERE id=?
                    """,
                    (datetime.now(timezone.utc).isoformat(), ticket_id),
                )
                connection.commit()

            self.assertFalse(ledger.verify_financial_ledger()[0])
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.get_ticket(ticket_id)

    def test_unexpected_trigger_cannot_use_next_write_as_signing_oracle(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            original_target = ledger.settings()["target_balance"]
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    """
                    CREATE TRIGGER poison
                    AFTER UPDATE OF stake_fraction_bps ON challenge_settings
                    BEGIN
                        UPDATE challenge_settings
                        SET target_balance_cents=1 WHERE id=1;
                    END
                    """
                )
                connection.commit()

            with self.assertRaisesRegex(RuntimeError, "integrity|checkpoint"):
                ledger.set_stake_fraction(0.10)
            with closing(sqlite3.connect(db_path)) as connection:
                stored_target = connection.execute(
                    "SELECT target_balance_cents FROM challenge_settings WHERE id=1"
                ).fetchone()[0]
            self.assertEqual(stored_target, round(original_target * 100))
            with self.assertRaisesRegex(RuntimeError, "integrity|checkpoint"):
                backup.verify_current_challenge_database(
                    db_path,
                    ledger._integrity_key_path.read_bytes(),
                    ledger_scope=str(db_path.resolve()),
                )

    def test_challenge_sequence_rewrite_is_detected_before_next_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "UPDATE sqlite_sequence SET seq=999 "
                    "WHERE name='challenge_transactions'"
                )
                connection.commit()

            with self.assertRaisesRegex(RuntimeError, "integrity|checkpoint"):
                ledger.set_stake_fraction(0.10)
            with self.assertRaisesRegex(RuntimeError, "integrity|checkpoint"):
                backup.verify_current_challenge_database(
                    db_path,
                    ledger._integrity_key_path.read_bytes(),
                    ledger_scope=str(db_path.resolve()),
                )

    def test_legitimate_settlement_correction_reversal_chain_reconciles(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id, ticket = _place_model_ticket(ledger, now)
            ledger.settle_ticket(ticket_id, "LOST")
            self.assertEqual(ledger.verify_financial_ledger(), (True, None))
            ledger.correct_settlement(
                ticket_id,
                "WON",
                settlement_odds=ticket.total_odds,
                reason="Provider correction verified",
            )
            self.assertEqual(ledger.verify_financial_ledger(), (True, None))
            ledger.reverse_settlement(
                ticket_id,
                reason="Settlement reopened for review",
            )
            self.assertEqual(ledger.verify_financial_ledger(), (True, None))
            ledger.settle_ticket(ticket_id, "LOST")
            self.assertEqual(ledger.verify_financial_ledger(), (True, None))
            backup.verify_current_challenge_database(
                db_path,
                ledger._integrity_key_path.read_bytes(),
                ledger_scope=str(db_path.resolve()),
            )

    def test_standalone_replay_rejects_validly_resigned_materialized_state(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id, _ticket = _place_model_ticket(ledger, now)
            ledger.settle_ticket(ticket_id, "LOST")
            forged_time = (now + timedelta(minutes=5)).isoformat()
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "DROP TRIGGER challenge_ticket_settlement_update_authorized"
                )
                connection.execute(
                    """
                    UPDATE challenge_tickets
                    SET status='WON', payout_cents=999900, settled_at=?,
                        settlement_odds=99.99,
                        settlement_note='valid checkpoint, impossible replay'
                    WHERE id=?
                    """,
                    (forged_time, ticket_id),
                )
                connection.commit()
            with closing(ledger._connect()) as connection:
                ledger._refresh_integrity_checkpoint(connection)
                connection.commit()

            with self.assertRaisesRegex(RuntimeError, "settlement|materialized"):
                backup.verify_current_challenge_database(
                    db_path,
                    ledger._integrity_key_path.read_bytes(),
                    ledger_scope=str(db_path.resolve()),
                )

    def test_settlement_source_tamper_fails_authenticated_chain(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id, _ticket = _place_model_ticket(ledger, now)
            ledger.settle_ticket(ticket_id, "LOST")
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "DROP TRIGGER challenge_settlement_events_no_update"
                )
                connection.execute(
                    """
                    UPDATE challenge_settlement_events
                    SET source='AUTO_PROVIDER_FT'
                    WHERE ticket_id=?
                    """,
                    (ticket_id,),
                )
                connection.commit()

            self.assertFalse(ledger.verify_financial_ledger()[0])
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.settlement_events(ticket_id)

    def test_fractional_settlement_integer_storage_fails_closed(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id, _ticket = _place_model_ticket(ledger, now)
            ledger.settle_ticket(ticket_id, "LOST")
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "DROP TRIGGER challenge_settlement_events_no_update"
                )
                connection.execute(
                    """
                    UPDATE challenge_settlement_events
                    SET previous_payout_cents=previous_payout_cents+0.5
                    WHERE ticket_id=?
                    """,
                    (ticket_id,),
                )
                storage_class = connection.execute(
                    """
                    SELECT typeof(previous_payout_cents)
                    FROM challenge_settlement_events WHERE ticket_id=?
                    """,
                    (ticket_id,),
                ).fetchone()[0]
                connection.commit()

            self.assertEqual(storage_class, "real")
            self.assertFalse(ledger.verify_financial_ledger()[0])
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.settings()

    def test_internal_hmac_writers_reject_fractional_integer_arguments(self):
        now = datetime.now(timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            ledger = ChallengeLedger(Path(tmp) / "challenge.db")
            with closing(ledger._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                with self.assertRaisesRegex(ValueError, "SQLite INTEGER"):
                    ledger._record_transaction(
                        connection,
                        created_at=now,
                        kind="BALANCE_ADJUSTMENT",
                        amount_cents=1.5,
                        balance_after_cents=10001,
                        note="fractional writer probe",
                    )
                with self.assertRaisesRegex(ValueError, "SQLite INTEGER"):
                    ledger._record_settlement_event(
                        connection,
                        ticket_id=1.5,
                        created_at=now,
                        action="SETTLE",
                        previous_status="PENDING",
                        new_status="LOST",
                        previous_payout_cents=0,
                        new_payout_cents=0,
                        settlement_odds=None,
                        source="MANUAL_CONFIRMED",
                        reason="fractional writer probe",
                    )
                connection.rollback()

    def test_fractional_storage_fails_in_each_authenticated_integer_domain(self):
        now = datetime.now(timezone.utc)
        cases = (
            (
                "settings",
                (),
                "UPDATE challenge_settings "
                "SET target_balance_cents=target_balance_cents+0.5 WHERE id=1",
            ),
            (
                "transaction",
                ("challenge_transactions_no_update",),
                "UPDATE challenge_transactions "
                "SET amount_cents=amount_cents+0.5 WHERE id=1",
            ),
            (
                "checkpoint",
                ("challenge_checkpoint_update_authorized",),
                "UPDATE challenge_integrity_checkpoint "
                "SET financial_count=financial_count+0.5 WHERE id=1",
            ),
        )
        for label, triggers, mutation in cases:
            with self.subTest(domain=label), tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "challenge.db"
                ledger = ChallengeLedger(db_path)
                with closing(sqlite3.connect(db_path)) as connection:
                    for trigger in triggers:
                        connection.execute(f"DROP TRIGGER {trigger}")
                    connection.execute(mutation)
                    connection.commit()
                self.assertFalse(ledger.verify_financial_ledger()[0])

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id, _ticket = _place_model_ticket(ledger, now)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "DROP TRIGGER challenge_ticket_v3_definition_immutable"
                )
                connection.execute(
                    "UPDATE challenge_tickets SET stake_cents=stake_cents+0.5 "
                    "WHERE id=?",
                    (ticket_id,),
                )
                connection.commit()
            self.assertFalse(ledger.verify_financial_ledger()[0])

        settlement_fields = (
            "previous_payout_cents",
            "new_payout_cents",
            "rule_version",
            "chain_version",
        )
        for field in settlement_fields:
            with self.subTest(settlement_field=field), tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "challenge.db"
                ledger = ChallengeLedger(db_path)
                ticket_id, _ticket = _place_model_ticket(ledger, now)
                ledger.settle_ticket(ticket_id, "LOST")
                with closing(sqlite3.connect(db_path)) as connection:
                    connection.execute(
                        "DROP TRIGGER challenge_settlement_events_no_update"
                    )
                    connection.execute(
                        f"UPDATE challenge_settlement_events "
                        f"SET {field}={field}+0.5 WHERE ticket_id=?",
                        (ticket_id,),
                    )
                    connection.commit()
                self.assertFalse(ledger.verify_financial_ledger()[0])

    def test_globally_authenticated_orphan_settlement_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            created_at = datetime.now(timezone.utc).isoformat()
            digest = _settlement_record_mac(
                ledger._integrity_key,
                ticket_id=999,
                created_at=created_at,
                action="SETTLE",
                previous_status="PENDING",
                new_status="LOST",
                previous_payout_cents=0,
                new_payout_cents=0,
                settlement_odds=None,
                rule_version=2,
                source="MANUAL_CONFIRMED",
                reason="Forged orphan",
                previous_hash=SETTLEMENT_ZERO_HASH,
            )
            with closing(sqlite3.connect(db_path)) as connection:
                connection.create_function(
                    "challenge_write_authorized",
                    0,
                    lambda: 1,
                    deterministic=True,
                )
                connection.execute("PRAGMA foreign_keys=OFF")
                cursor = connection.execute(
                    """
                    INSERT INTO challenge_settlement_events (
                        ticket_id, created_at, action, previous_status,
                        new_status, previous_payout_cents,
                        new_payout_cents, settlement_odds, rule_version,
                        source, reason, chain_version, previous_hash, record_hash
                    ) VALUES (999, ?, 'SETTLE', 'PENDING', 'LOST', 0, 0,
                              NULL, 2, 'MANUAL_CONFIRMED', 'Forged orphan',
                              ?, ?, ?)
                    """,
                    (
                        created_at,
                        SETTLEMENT_CHAIN_VERSION,
                        SETTLEMENT_ZERO_HASH,
                        digest,
                    ),
                )
                orphan_id = int(cursor.lastrowid)
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET settlement_anchor_hash=? WHERE id=1
                    """,
                    (digest,),
                )
                connection.commit()

            self.assertEqual(
                ledger.verify_financial_ledger(),
                (False, orphan_id),
            )
            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ledger.settings()

    def test_legacy_migration_snapshot_is_idempotent_anchor(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "legacy.db"
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    """
                    CREATE TABLE challenge_settings (
                        id INTEGER PRIMARY KEY,
                        starting_balance_cents INTEGER NOT NULL,
                        current_balance_cents INTEGER NOT NULL,
                        target_balance_cents INTEGER NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "INSERT INTO challenge_settings VALUES (1, 10000, 8750, 1500000, 'legacy')"
                )
                connection.execute(
                    """
                    CREATE TABLE challenge_tickets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        analysis_date TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        quote_verified_at TEXT NOT NULL,
                        settled_at TEXT,
                        status TEXT NOT NULL,
                        stake_cents INTEGER NOT NULL,
                        payout_cents INTEGER NOT NULL DEFAULT 0,
                        total_odds REAL NOT NULL,
                        joint_probability REAL NOT NULL,
                        expected_roi REAL NOT NULL,
                        legs_json TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    INSERT INTO challenge_tickets (
                        analysis_date, created_at, quote_verified_at, settled_at,
                        status, stake_cents, payout_cents, total_odds,
                        joint_probability, expected_roi, legs_json
                    ) VALUES (?, ?, ?, ?, 'LOST', 1250, 0, 2.0, 0.0, -1.0, ?)
                    """,
                    (
                        "2026-08-20",
                        "2026-08-20T08:00:00+00:00",
                        "2026-08-20T08:00:00+00:00",
                        "2026-08-20T12:00:00+00:00",
                        json.dumps([{"manual": True, "label": "Legacy"}]),
                    ),
                )
                connection.commit()

            first = ChallengeLedger(db_path)
            second = ChallengeLedger(db_path)
            transactions = second.transactions()

            self.assertEqual(len(transactions), 1)
            self.assertEqual(transactions[0]["kind"], "MIGRATION_SNAPSHOT")
            self.assertEqual(transactions[0]["amount"], 0.0)
            self.assertEqual(transactions[0]["balance_after"], 87.5)
            self.assertEqual(second.verify_financial_ledger(), (True, None))
            legacy = first.get_ticket(1)
            self.assertEqual(legacy["definition_version"], 0)
            self.assertEqual(legacy["entry_source"], "MANUAL")
            settings = second.settings()
            self.assertEqual(
                settings["financial_chain_version"],
                FINANCIAL_CHAIN_VERSION,
            )
            self.assertEqual(
                settings["settlement_chain_version"],
                SETTLEMENT_CHAIN_VERSION,
            )
            self.assertEqual(
                settings["financial_anchor_hash"],
                transactions[0]["record_hash"],
            )
            self.assertEqual(transactions[0]["previous_hash"], FINANCIAL_ZERO_HASH)
            self.assertEqual(len(transactions[0]["record_hash"]), 64)

    def test_partial_financial_hash_migration_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ChallengeLedger(db_path)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "DROP TRIGGER challenge_transactions_no_update"
                )
                connection.execute(
                    "UPDATE challenge_transactions SET record_hash=NULL WHERE id=1"
                )
                connection.commit()

            with self.assertRaisesRegex(RuntimeError, "HMAC chain is incomplete"):
                ChallengeLedger(db_path)

    def test_public_sha_v1_downgrade_is_never_resigned(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            first = ChallengeLedger(db_path)
            first.transactions()
            with closing(sqlite3.connect(db_path)) as connection:
                _downgrade_financial_chain_to_precheckpoint_v1(connection)
                connection.commit()

            with patch.dict(
                os.environ,
                {LEDGER_CHECKPOINT_MIGRATION_ENV: "1"},
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "unsupported|checkpoint",
                ):
                    ChallengeLedger(db_path)

    def test_unsigned_hmac_era_settlement_history_is_not_resigned(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ticket_id, _ticket = _place_model_ticket(ledger, now)
            ledger.settle_ticket(ticket_id, "LOST")
            with closing(sqlite3.connect(db_path)) as connection:
                _downgrade_financial_chain_to_precheckpoint_v1(connection)
                connection.execute(
                    "DROP TRIGGER challenge_settlement_events_no_update"
                )
                connection.execute(
                    "DROP TRIGGER challenge_settlement_anchor_immutable"
                )
                connection.execute(
                    """
                    UPDATE challenge_settlement_events
                    SET chain_version=0, previous_hash=NULL, record_hash=NULL
                    """
                )
                connection.execute(
                    """
                    UPDATE challenge_settings
                    SET settlement_chain_version=0,
                        settlement_anchor_hash=NULL
                    WHERE id=1
                    """
                )
                connection.commit()

            with patch.dict(
                os.environ,
                {LEDGER_CHECKPOINT_MIGRATION_ENV: "1"},
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "unsupported|checkpoint",
                ):
                    ChallengeLedger(db_path)

    def test_production_mode_requires_preprovisioned_external_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop(LEDGER_HMAC_KEY_FILE_ENV, None)
                os.environ[LEDGER_HMAC_REQUIRED_ENV] = "1"
                with self.assertRaisesRegex(RuntimeError, "required in production"):
                    ChallengeLedger(db_path)

    def test_wrong_external_key_fails_closed_without_resigning_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            key_path = ledger._integrity_key_path
            key_path.write_bytes(b"ab" * 32 + b"\n")

            with self.assertRaisesRegex(RuntimeError, "financial ledger"):
                ChallengeLedger(db_path)

    def test_deleted_checkpoint_cannot_be_silently_recreated(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ChallengeLedger(db_path)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute("DROP TABLE challenge_integrity_checkpoint")
                connection.commit()

            with self.assertRaisesRegex(RuntimeError, "missing.*checkpoint"):
                ChallengeLedger(db_path)
            with patch.dict(
                os.environ,
                {LEDGER_CHECKPOINT_MIGRATION_ENV: "1"},
            ):
                with self.assertRaisesRegex(RuntimeError, "missing.*checkpoint"):
                    ChallengeLedger(db_path)

    def test_deleted_checkpoint_row_fails_even_in_migration_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ChallengeLedger(db_path)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "DROP TRIGGER challenge_checkpoint_no_delete"
                )
                connection.execute(
                    "DELETE FROM challenge_integrity_checkpoint WHERE id=1"
                )
                connection.commit()

            with patch.dict(
                os.environ,
                {LEDGER_CHECKPOINT_MIGRATION_ENV: "1"},
            ):
                with self.assertRaisesRegex(RuntimeError, "checkpoint precheck"):
                    ChallengeLedger(db_path)

    def test_signed_database_cannot_be_replayed_in_another_account_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "account-a.db"
            destination = root / "account-b.db"
            ChallengeLedger(source)
            shutil.copy2(source, destination)

            with self.assertRaisesRegex(RuntimeError, "checkpoint precheck"):
                ChallengeLedger(destination)

    def test_concurrent_local_ledgers_publish_one_complete_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def open_ledger(index: int) -> bytes:
                return ChallengeLedger(root / f"account-{index}.db")._integrity_key

            with ThreadPoolExecutor(max_workers=12) as executor:
                keys = list(executor.map(open_ledger, range(24)))

            self.assertEqual(len(set(keys)), 1)
            key_path = root / ".betboy-ledger-hmac.key"
            self.assertEqual(key_path.read_text(encoding="ascii").strip(), keys[0].hex())
            self.assertEqual(key_path.stat().st_nlink, 1)
            self.assertEqual(list(root.glob("*.partial")), [])


class WholeDatabaseCheckpointTests(unittest.TestCase):
    def test_application_and_backup_bind_the_same_complete_user_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ChallengeLedger(db_path)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.row_factory = sqlite3.Row
                application_manifest = _challenge_schema_manifest(connection)
                backup_manifest = backup._challenge_schema_manifest(connection)

            self.assertEqual(application_manifest, backup_manifest)
            names = {record["name"] for record in application_manifest}
            self.assertIn("price_observations", names)
            self.assertIn("sqlite_sequence", names)
            self.assertIn("sqlite_autoindex_price_observations_1", names)

    def test_prefixless_extra_schema_objects_break_app_and_backup_hmac(self):
        definitions = {
            "table": "CREATE TABLE evil_table (id INTEGER PRIMARY KEY)",
            "view": (
                "CREATE VIEW evil_view AS "
                "SELECT id FROM challenge_settings"
            ),
            "trigger": (
                "CREATE TRIGGER evil_trigger AFTER UPDATE ON challenge_settings "
                "BEGIN SELECT 1; END"
            ),
            "sqlite_without_reserved_underscore": (
                "CREATE TABLE sqliteevil (id INTEGER PRIMARY KEY)"
            ),
        }
        for label, ddl in definitions.items():
            with self.subTest(object=label), tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "challenge.db"
                ledger = ChallengeLedger(db_path)
                key_bytes = ledger._integrity_key_path.read_bytes()
                with closing(sqlite3.connect(db_path)) as connection:
                    connection.execute(ddl)
                    connection.commit()

                with self.assertRaisesRegex(RuntimeError, "integrity"):
                    ledger.settings()
                with self.assertRaisesRegex(RuntimeError, "checkpoint HMAC"):
                    backup.verify_current_challenge_database(
                        db_path,
                        key_bytes,
                        ledger_scope=str(db_path.resolve()),
                    )

    def test_writable_schema_internal_object_is_not_hidden_by_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            key_bytes = ledger._integrity_key_path.read_bytes()
            with closing(sqlite3.connect(db_path)) as connection:
                connection.row_factory = sqlite3.Row
                connection.execute("PRAGMA writable_schema=ON")
                connection.execute(
                    "INSERT INTO sqlite_master(type,name,tbl_name,rootpage,sql) "
                    "VALUES('index','sqlite_injected_index',"
                    "'challenge_settings',0,NULL)"
                )
                connection.commit()
                try:
                    names = {
                        record["name"]
                        for record in _challenge_schema_manifest(connection)
                    }
                    self.assertIn("sqlite_injected_index", names)
                    self.assertFalse(
                        ledger._verify_integrity_checkpoint(connection)[0]
                    )
                    with self.assertRaises(RuntimeError):
                        backup.verify_current_challenge_database(
                            db_path,
                            key_bytes,
                            ledger_scope=str(db_path.resolve()),
                        )
                finally:
                    connection.execute(
                        "DELETE FROM sqlite_master "
                        "WHERE name='sqlite_injected_index'"
                    )
                    connection.execute("PRAGMA writable_schema=OFF")
                    connection.commit()

    def test_all_dedicated_sequences_have_app_backup_parity(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            _place_model_ticket(ledger, now)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.row_factory = sqlite3.Row
                application_state = _challenge_sequence_state(connection)
                backup_state = backup._challenge_sequence_state(connection)

            self.assertEqual(application_state, backup_state)
            names = {record["name"] for record in application_state}
            self.assertIn("price_observations", names)
            self.assertIn("challenge_transactions", names)
            self.assertIn("challenge_tickets", names)

    def test_price_and_unknown_sequence_tamper_break_app_and_backup(self):
        mutations = {
            "price": (
                "UPDATE sqlite_sequence SET seq=seq+1 "
                "WHERE name='price_observations'"
            ),
            "unknown": (
                "INSERT INTO sqlite_sequence(name, seq) "
                "VALUES('forged_sequence', 7)"
            ),
        }
        for label, statement in mutations.items():
            with self.subTest(sequence=label), tempfile.TemporaryDirectory() as tmp:
                db_path = Path(tmp) / "challenge.db"
                ledger = ChallengeLedger(db_path)
                _place_model_ticket(ledger, datetime.now(timezone.utc))
                key_bytes = ledger._integrity_key_path.read_bytes()
                with closing(sqlite3.connect(db_path)) as connection:
                    connection.execute(statement)
                    connection.commit()

                with self.assertRaisesRegex(RuntimeError, "integrity"):
                    ledger.settings()
                with self.assertRaisesRegex(
                    RuntimeError,
                    "sequence|checkpoint HMAC",
                ):
                    backup.verify_current_challenge_database(
                        db_path,
                        key_bytes,
                        ledger_scope=str(db_path.resolve()),
                    )

    def test_price_checkpoint_reconcile_accepts_only_exact_call_delta(self):
        now = datetime.now(timezone.utc)
        item = _candidate(now)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ledger.settings()
            prices = PriceLedger(db_path)

            def append(selection_suffix: str):
                return prices.append(
                    PriceQuote(
                        sport="FOOTBALL",
                        event_id=str(item.fixture_id),
                        event_name=f"{item.home_team} vs {item.away_team}",
                        scheduled_start=item.kickoff,
                        market_key=item.market_key,
                        market_name=item.market,
                        selection_key=f"{item.candidate_id}:{selection_suffix}",
                        selection_name=item.selection,
                        decimal_odds=2.10,
                        captured_at=now,
                        model_ref=CHALLENGE_MODEL_CONTRACT_SIGNATURE,
                    ),
                    now=now,
                )

            expected = append("expected")
            append("injected")
            with closing(ledger._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                with self.assertRaisesRegex(
                    RuntimeError,
                    "sequence advance",
                ):
                    ledger._reconcile_authenticated_price_appends(
                        connection,
                        [prices.append_receipt(expected.id)],
                    )
                connection.rollback()

    def test_ticket_price_append_rolls_back_with_ticket_transaction_failure(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            _item, ticket = _model_ticket(now)
            original = ledger._verified_quote_observation_ids

            def crash_after_price_append(*args, **kwargs):
                result = original(*args, **kwargs)
                raise RuntimeError("simulated crash after price append")

            with patch.object(
                ledger,
                "_verified_quote_observation_ids",
                side_effect=crash_after_price_append,
            ):
                with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                    ledger.place_ticket(
                        now.date().isoformat(),
                        ticket,
                        ticket_stake(ticket, 100.0),
                        now.isoformat(),
                    )

            with closing(sqlite3.connect(db_path)) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM price_observations").fetchone()[0],
                    0,
                )
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM challenge_tickets").fetchone()[0],
                    0,
                )
            self.assertEqual(
                ChallengeLedger(db_path).settings()["current_balance"],
                100.0,
            )

    def test_concurrent_ticket_attempts_commit_one_atomic_price_and_ticket(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledgers = (ChallengeLedger(db_path), ChallengeLedger(db_path))
            tickets = (_model_ticket(now)[1], _model_ticket(now)[1])
            append_barrier = Barrier(2)
            original_append = PriceLedger.append

            def synchronized_standalone_append(price_ledger, *args, **kwargs):
                observation = original_append(price_ledger, *args, **kwargs)
                if kwargs.get("connection") is None:
                    append_barrier.wait(timeout=10)
                return observation

            def place(index: int):
                ticket = tickets[index]
                try:
                    return (
                        "placed",
                        ledgers[index].place_ticket(
                            now.date().isoformat(),
                            ticket,
                            ticket_stake(ticket, 100.0),
                            now.isoformat(),
                        ),
                    )
                except ValueError as exc:
                    return ("rejected", str(exc))

            with patch.object(PriceLedger, "append", new=synchronized_standalone_append):
                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(place, range(2)))

            self.assertEqual([result[0] for result in results].count("placed"), 1)
            self.assertEqual([result[0] for result in results].count("rejected"), 1)
            reopened = ChallengeLedger(db_path)
            self.assertEqual(len(reopened.tickets()), 1)
            with closing(sqlite3.connect(db_path)) as connection:
                self.assertEqual(
                    connection.execute("SELECT COUNT(*) FROM price_observations").fetchone()[0],
                    1,
                )

    def test_price_reconcile_rejects_post_append_row_rewrite_and_rehash(self):
        now = datetime.now(timezone.utc)
        item = _candidate(now)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ledger.settings()
            prices = PriceLedger(db_path)
            observation = prices.append(
                PriceQuote(
                    sport="FOOTBALL",
                    event_id=str(item.fixture_id),
                    event_name=f"{item.home_team} vs {item.away_team}",
                    scheduled_start=item.kickoff,
                    market_key=item.market_key,
                    market_name=item.market,
                    selection_key=item.candidate_id,
                    selection_name=item.selection,
                    decimal_odds=2.10,
                    captured_at=now,
                    model_ref=CHALLENGE_MODEL_CONTRACT_SIGNATURE,
                ),
                now=now,
            )
            expected_receipt = prices.append_receipt(observation.id)
            with closing(sqlite3.connect(db_path)) as connection:
                connection.row_factory = sqlite3.Row
                trigger_sql = connection.execute(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type='trigger' AND name='price_observations_no_update'"
                ).fetchone()[0]
                row = connection.execute(
                    "SELECT * FROM price_observations WHERE id=?",
                    (observation.id,),
                ).fetchone()
                forged_payload = _price_row_payload(row)
                forged_payload["source"] = "API"
                forged_payload["metadata_json"] = '{"injected":true}'
                forged_hash = _price_record_hash(forged_payload)
                connection.execute("DROP TRIGGER price_observations_no_update")
                connection.execute(
                    "UPDATE price_observations "
                    "SET source='API', metadata_json=?, record_hash=? WHERE id=?",
                    ('{"injected":true}', forged_hash, observation.id),
                )
                connection.execute(trigger_sql)
                connection.commit()

            with closing(ledger._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                with self.assertRaisesRegex(
                    RuntimeError,
                    "sequence advance",
                ):
                    ledger._reconcile_authenticated_price_appends(
                        connection,
                        [expected_receipt],
                    )
                connection.rollback()

    def test_price_reconcile_rejects_sequence_prebump_before_append(self):
        now = datetime.now(timezone.utc)
        item = _candidate(now)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ledger.settings()
            with closing(sqlite3.connect(db_path)) as connection:
                connection.execute(
                    "INSERT INTO sqlite_sequence(name, seq) "
                    "VALUES('price_observations', 5)"
                )
                connection.commit()
            prices = PriceLedger(db_path)
            observation = prices.append(
                PriceQuote(
                    sport="FOOTBALL",
                    event_id=str(item.fixture_id),
                    event_name=f"{item.home_team} vs {item.away_team}",
                    scheduled_start=item.kickoff,
                    market_key=item.market_key,
                    market_name=item.market,
                    selection_key=item.candidate_id,
                    selection_name=item.selection,
                    decimal_odds=2.10,
                    captured_at=now,
                    model_ref=CHALLENGE_MODEL_CONTRACT_SIGNATURE,
                ),
                now=now,
            )
            with closing(ledger._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                with self.assertRaisesRegex(
                    RuntimeError,
                    "sequence advance",
                ):
                    ledger._reconcile_authenticated_price_appends(
                        connection,
                        [prices.append_receipt(observation.id)],
                    )
                connection.rollback()

    def test_middle_price_row_rewrite_breaks_runtime_and_backup_verifiers(self):
        now = datetime.now(timezone.utc)
        item = _candidate(now)
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "challenge.db"
            ledger = ChallengeLedger(db_path)
            ledger.settings()
            prices = PriceLedger(db_path)
            observations = [
                prices.append(
                    PriceQuote(
                        sport="FOOTBALL",
                        event_id=str(item.fixture_id),
                        event_name=f"{item.home_team} vs {item.away_team}",
                        scheduled_start=item.kickoff,
                        market_key=item.market_key,
                        market_name=item.market,
                        selection_key=f"{item.candidate_id}:{index}",
                        selection_name=item.selection,
                        decimal_odds=2.10 + index / 100,
                        captured_at=now,
                        model_ref=CHALLENGE_MODEL_CONTRACT_SIGNATURE,
                    ),
                    now=now,
                )
                for index in range(3)
            ]
            with closing(ledger._connect()) as connection:
                connection.execute("BEGIN IMMEDIATE")
                ledger._reconcile_authenticated_price_appends(
                    connection,
                    [
                        prices.append_receipt(observation.id)
                        for observation in observations
                    ],
                )
                connection.commit()
            key_bytes = ledger._integrity_key_path.read_bytes()

            with closing(sqlite3.connect(db_path)) as connection:
                trigger_sql = connection.execute(
                    "SELECT sql FROM sqlite_master "
                    "WHERE type='trigger' AND name='price_observations_no_update'"
                ).fetchone()[0]
                connection.execute("DROP TRIGGER price_observations_no_update")
                connection.execute(
                    "UPDATE price_observations SET event_name='tampered' WHERE id=2"
                )
                connection.execute(trigger_sql)
                connection.commit()

            with self.assertRaisesRegex(RuntimeError, "integrity"):
                ledger.settings()
            with self.assertRaisesRegex(RuntimeError, "Price observation hash chain"):
                backup.verify_current_challenge_database(
                    db_path,
                    key_bytes,
                    ledger_scope=str(db_path.resolve()),
                )


class BackupMigrationReceiptInventoryTests(unittest.TestCase):
    def test_stale_manifest_repack_of_non_challenge_database_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            database = base / "runtime.db"
            _create_plain_database(database)
            original = database.read_bytes()
            key = b"ab" * 32 + b"\n"
            manifest = {
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source_head": "a" * 40,
                "database_count": 1,
                "databases": [
                    {
                        "path": "runtime.db",
                        "source_size": len(original),
                        "backup_size": len(original),
                        "sha256": hashlib.sha256(original).hexdigest(),
                    }
                ],
                "integrity_key": {
                    "path": backup.INTEGRITY_KEY_ARCHIVE_PATH,
                    "sha256": hashlib.sha256(key).hexdigest(),
                },
            }
            valid_archive = base / "valid-manifest.zip"
            with zipfile.ZipFile(valid_archive, "w") as zipped:
                zipped.writestr("runtime.db", original)
                zipped.writestr(backup.INTEGRITY_KEY_ARCHIVE_PATH, key)
                zipped.writestr(
                    "MANIFEST.json",
                    json.dumps(manifest, sort_keys=True),
                )
            self.assertEqual(backup.verify_archive(valid_archive), 1)

            with closing(sqlite3.connect(database)) as connection:
                connection.execute(
                    "INSERT INTO runtime_state(id, value) VALUES(1, 'repacked')"
                )
                connection.commit()
            archive = base / "stale-manifest.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.write(database, "runtime.db")
                zipped.writestr(backup.INTEGRITY_KEY_ARCHIVE_PATH, key)
                zipped.writestr(
                    "MANIFEST.json",
                    json.dumps(manifest, sort_keys=True),
                )

            with self.assertRaisesRegex(RuntimeError, "manifest.*digest"):
                backup.verify_archive(archive)

    def test_create_archive_rejects_missing_renamed_and_emptied_receipt_db(self):
        for mutation in ("missing", "renamed", "emptied"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                root, challenge_path, key_path, marker_path = _build_backup_fixture(
                    base
                )
                if mutation == "missing":
                    challenge_path.unlink()
                elif mutation == "renamed":
                    challenge_path.rename(root / "renamed.db")
                else:
                    challenge_path.unlink()
                    with closing(sqlite3.connect(challenge_path)) as connection:
                        connection.execute("PRAGMA user_version=1")
                        connection.commit()

                with self.assertRaisesRegex(
                    RuntimeError,
                    "receipt|challenge_settings|checkpoint",
                ):
                    backup.create_archive(
                        base / "backups",
                        root=root,
                        integrity_key_path=key_path,
                        migration_marker_path=marker_path,
                    )

    def test_verify_archive_rejects_missing_renamed_and_emptied_receipt_member(self):
        for mutation in ("missing", "renamed", "emptied"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                root, _challenge_path, key_path, marker_path = _build_backup_fixture(
                    base
                )
                valid_archive, _ = backup.create_archive(
                    base / "backups",
                    root=root,
                    integrity_key_path=key_path,
                    migration_marker_path=marker_path,
                )
                empty_database = base / "empty.db"
                with closing(sqlite3.connect(empty_database)) as connection:
                    connection.execute("PRAGMA user_version=1")
                    connection.commit()
                tampered = base / f"tampered-{mutation}.zip"
                with zipfile.ZipFile(valid_archive) as source, zipfile.ZipFile(
                    tampered,
                    "w",
                    compression=zipfile.ZIP_DEFLATED,
                ) as destination:
                    for info in source.infolist():
                        data = source.read(info)
                        name = info.filename
                        if name == "challenge_15k.db":
                            if mutation == "missing":
                                continue
                            if mutation == "renamed":
                                name = "renamed.db"
                            else:
                                data = empty_database.read_bytes()
                        destination.writestr(name, data)

                with self.assertRaisesRegex(
                    RuntimeError,
                    "receipt|challenge_settings|checkpoint",
                ):
                    backup.verify_archive(tampered)


if __name__ == "__main__":
    unittest.main()
