"""Bounded read-only inventory of native tennis context, never qualification.

One earliest real pre-match original per event, not one case per polling run.
This diagnostic does not fit, publish artifacts, call providers or open an
experiment's opaque test labels. Result payloads are used only to verify native
identity and normal completion; winners are not returned or scored.
"""
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
import json
import sqlite3
from time import monotonic

from context_models.contracts import ContextContractError, ContextIntegrityError, canonical_timestamp
from context_models.dataset import _reader, _artifact
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND, original_base, validate_original_publication
from context_models.tennis_v4 import tennis_features_v4
from context_observations import _SELECT, _decode_receipt
from context_sources.outcomes import validate_outcome_record
from context_sources.tennis_status import STATUS_SCHEMA, validate_selected_tennis_receipt
from context_sources.tennis import SOURCE_SCHEMA


@contextmanager
def _deadline_reader(path, *, cancelled):
    """Own only this diagnostic's interruption, not other database failures."""
    try:
        with _reader(path) as connection:
            try:
                yield connection
            finally:
                # An expired progress handler must not interrupt rollback and
                # replace the original error while the owning reader closes.
                connection.set_progress_handler(None, 0)
    except ContextIntegrityError as exc:
        cause = exc.__cause__
        if (cancelled() and isinstance(cause, sqlite3.OperationalError)
                and getattr(cause, 'sqlite_errorcode', None) == sqlite3.SQLITE_INTERRUPT):
            raise TimeoutError('native context readiness time budget exhausted') from exc
        raise


def audit_tennis_readiness(path, *, as_of, sample_limit=25, seconds=120, progress=None,
                           inventory_only=False, all_features=False, event_offset=0, event_count=None,
                           membership_mode='indexed'):
    from context_models.tennis_training import _validate_membership_mode
    _validate_membership_mode(membership_mode)
    if type(inventory_only) is not bool or type(all_features) is not bool:
        raise ValueError('inventory_only and all_features must be boolean')
    if inventory_only and all_features:
        raise ValueError('inventory_only and all_features are mutually exclusive')
    if type(event_offset) is not int or event_offset < 0 or (
            event_count is not None and (type(event_count) is not int or not 1 <= event_count <= 100)):
        raise ValueError('feature inventory range requires a nonnegative offset and 1 to 100 events')
    if not all_features and (event_offset != 0 or event_count is not None):
        raise ValueError('feature inventory ranges require all_features')
    if type(sample_limit) is not int or not 1 <= sample_limit <= 100:
        raise ValueError('sample_limit must be between 1 and 100')
    if type(seconds) not in (int, float) or not 1 <= seconds <= 600:
        raise ValueError('seconds must be between 1 and 600')
    clock = canonical_timestamp(as_of)
    started = monotonic()
    sql_cancelled = False
    def budget():
        if monotonic()-started > seconds:
            raise TimeoutError('native context readiness time budget exhausted')
    def sql_budget():
        nonlocal sql_cancelled
        sql_cancelled = monotonic()-started > seconds
        return int(sql_cancelled)
    with _deadline_reader(path, cancelled=lambda: sql_cancelled) as conn:
        conn.set_progress_handler(sql_budget, 10000)
        kinds = dict(conn.execute('SELECT kind,count(*) FROM artifacts GROUP BY kind'))
        originals = {}
        publications = 0
        late = 0
        for ref, created in conn.execute('SELECT digest,created_at FROM artifacts WHERE kind=? AND created_at<=? ORDER BY created_at,digest',
                (ORIGINAL_ARTIFACT_KIND, clock)).fetchall():
            budget()
            artifact = _artifact(conn, ref, ORIGINAL_ARTIFACT_KIND, latest=clock)
            origin = validate_original_publication(artifact['payload'], created_at=created)['origin']
            publications += 1
            if created >= origin['event']['scheduled_start']:
                late += 1
                continue
            event_key = origin['event']['event_key']
            candidate = (origin['cutoff'], ref, created, origin)
            if event_key not in originals or candidate[:2] < originals[event_key][:2]:
                originals[event_key] = candidate
        matched, exclusions = [], Counter()
        for _, ref, created, origin in sorted(originals.values(), key=lambda item: item[:2]):
            budget()
            raw_rows = conn.execute(_SELECT+" WHERE r.event_key=? AND r.kind='match_outcome' AND r.observed_at<=? ORDER BY r.observed_at,r.digest",
                (origin['event']['event_key'], clock)).fetchall()
            if not raw_rows:
                exclusions['no_native_outcome'] += 1
                continue
            latest = max(row[3] for row in raw_rows)
            finals = []
            for raw in raw_rows:
                # All selected physical bytes are checked, including old revisions.
                row = _decode_receipt(raw)
                if row['observed_at'] != latest:
                    continue
                row.update(evidence_class='prospective', effective_at=row['observed_at'], publication_resolution=None)
                try:
                    validate_outcome_record(row, event=origin['event'])
                except ContextContractError:
                    exclusions['native_outcome_binding_mismatch'] += 1
                    continue
                if created >= row['payload'].get('reported_scheduled_start', origin['event']['scheduled_start']):
                    exclusions['original_after_reported_start'] += 1
                    continue
                finals.append(row)
            if len(finals) != 1:
                exclusions['no_unique_matching_final'] += 1
                continue
            matched.append((ref, origin))
        # Spread the bounded diagnostic across the whole time-ordered inventory;
        # selection does not inspect winners, probabilities or feature values.
        range_start = min(event_offset, len(matched))
        range_stop = min(range_start+(event_count or len(matched)), len(matched))
        count = min(sample_limit, len(matched))
        positions = (range(range_start, range_stop) if all_features else
                     [0] if count == 1 else [i*(len(matched)-1)//(count-1) for i in range(count)])
        sample = [matched[i] for i in positions]
        tours = {}
        for ref, origin in matched:
            tour = origin['event']['tour']
            cohort = tours.setdefault(tour, {'matching_final_events': 0, 'decision_days': {}})
            cohort['matching_final_events'] += 1
            day = origin['cutoff'][:10]
            cohort['decision_days'][day] = cohort['decision_days'].get(day, 0) + 1
        for cohort in tours.values():
            cohort['meets_test_count_floor_only'] = cohort['matching_final_events'] >= 200
        inventory = {'schema': 1, 'as_of': clock, 'kind': 'native-readiness-not-empirical-qualification',
            'original_publications': publications, 'unique_original_events': len(originals),
            'late_original_publications': late, 'matching_final_events': len(matched),
            'outcome_exclusions': dict(exclusions), 'artifact_kinds': kinds, 'tour_cohorts': tours,
            'minimum_untouched_test_events': 200, 'total_events_meet_test_count_floor_only': len(matched) >= 200,
            'qualified': False, 'reason': 'inventory_only_no_train_tune_test_improvement_evaluation'}
        if progress:
            progress({'phase':'inventory', 'unique_original_events':len(originals), 'matching_final_events':len(matched), 'sample':len(sample)})
        if inventory_only:
            return {**inventory, 'sample': [], 'sample_limited': bool(matched),
                'sample_policy': 'inventory-only-no-feature-or-score-evaluation',
                'elapsed_seconds': round(monotonic()-started, 3)}
        results, feature_cohorts = [], {}
        from context_models.tennis_training import _TennisBatchBudget, iter_live_tennis_features
        shared_budget = _TennisBatchBudget(seconds, started=started)
        if membership_mode == 'indexed' and not sample:
            from context_tennis_index import _verified_index_state
            _verified_index_state(conn)
        if len(sample) > 100:
            raise ValueError('feature batch requires at most 100 events; use an explicit inventory range')
        feature_rows = (iter_live_tennis_features(conn, tuple(origin for _, origin in sample), budget=shared_budget,
                                                membership_mode=membership_mode)
                        if sample else ())
        for owner, observations, features in feature_rows:
            ref, origin = sample[len(results)]
            budget()
            event = origin['event']
            cohort = feature_cohorts.setdefault(event['tour'], {
                'evaluated_events': 0, 'available': Counter(), 'nonzero': Counter(),
                'both_players_complete_sets_3d': 0, 'coverage': Counter(),
                'decision_days': Counter(),
            })
            cohort['evaluated_events'] += 1
            cohort['coverage'][json.dumps(features['coverage'], sort_keys=True, separators=(',', ':'))] += 1
            cohort['decision_days'][origin['cutoff'][:10]] += 1
            for name, value in features['values'].items():
                cohort['available'].setdefault(name, 0)
                cohort['nonzero'].setdefault(name, 0)
                if value is not None and features['states'][name] == 'available' and features['refs'][name]:
                    cohort['available'][name] += 1
                    cohort['nonzero'][name] += int(value != 0)
            cohort['both_players_complete_sets_3d'] += int(all(
                features['values'][name] == 1 and features['states'][name] == 'available'
                for name in ('bounded_sets_complete_3d_a', 'bounded_sets_complete_3d_b')))
            measured = {}
            for name in ('bounded_sets_1d_delta', 'bounded_sets_3d_delta', 'bounded_games_3d_delta',
                         'bounded_minutes_3d_delta', 'observed_recovery_minimum_hours_delta',
                         'bounded_recovery_minimum_hours_delta'):
                measured[name] = features['values'][name]
            complete = {name: features['values'][name] for name in (
                'bounded_sets_complete_1d_a', 'bounded_sets_complete_1d_b',
                'bounded_sets_complete_3d_a', 'bounded_sets_complete_3d_b')}
            results.append({'event_key':event['event_key'], 'tour':event['tour'], 'original_ref':ref,
                'cutoff':origin['cutoff'], 'references':len(owner.observation_refs), 'coverage':features['coverage'],
                'measured':measured, 'complete_observed_subset':complete})
            if progress:
                progress({'phase':'features', 'completed':len(results), 'total':len(sample)})
            del owner, observations, features
        return {**inventory, 'sample':results, 'feature_cohorts': feature_cohorts,
            'sample_limited':len(matched)>len(sample),
            **({'feature_inventory_range': {'start': range_start, 'stop': range_stop}} if all_features else {}),
            'sample_policy': ('consecutive-range-earliest-original-time-order' if all_features and event_count is not None
                              else 'all-earliest-original-events-no-outcome-scoring' if all_features
                              else 'evenly-spaced-earliest-original-time-order'),
            'elapsed_seconds':round(monotonic()-started,3)}
