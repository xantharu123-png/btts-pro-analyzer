"""Bounded read-only inventory of native tennis context, never qualification.

One earliest real pre-match original per event, not one case per polling run.
This diagnostic does not fit, publish artifacts, call providers or open an
experiment's opaque test labels. Result payloads are used only to verify native
identity and normal completion; winners are not returned or scored.
"""
from collections import Counter
from datetime import datetime
import json
from time import monotonic

from context_models.contracts import ContextContractError, canonical_timestamp
from context_models.dataset import _reader, _artifact
from context_models.tennis_live import ORIGINAL_ARTIFACT_KIND, original_base, validate_original_publication
from context_models.tennis_v4 import tennis_features_v4
from context_observations import _SELECT, _decode_receipt
from context_sources.outcomes import validate_outcome_record
from context_sources.tennis_status import STATUS_SCHEMA, validate_selected_tennis_receipt
from context_sources.tennis import SOURCE_SCHEMA


def audit_tennis_readiness(path, *, as_of, sample_limit=25, seconds=120, progress=None):
    if type(sample_limit) is not int or not 1 <= sample_limit <= 100:
        raise ValueError('sample_limit must be between 1 and 100')
    if type(seconds) not in (int, float) or not 1 <= seconds <= 600:
        raise ValueError('seconds must be between 1 and 600')
    clock = canonical_timestamp(as_of)
    started = monotonic()
    def budget():
        if monotonic()-started > seconds:
            raise TimeoutError('native context readiness time budget exhausted')
    with _reader(path) as conn:
        conn.set_progress_handler(lambda: int(monotonic()-started > seconds), 10000)
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
        count = min(sample_limit, len(matched))
        positions = ([0] if count == 1 else [i*(len(matched)-1)//(count-1) for i in range(count)])
        sample = [matched[i] for i in positions]
        if progress:
            progress({'phase':'inventory', 'unique_original_events':len(originals), 'matching_final_events':len(matched), 'sample':len(sample)})
        # Index DISTINCT source content once, rather than parse an unchanged
        # JSON body again for each of its many receipt revisions and each card.
        players = {p for _, origin in sample for p in (origin['event']['home_id'], origin['event']['away_id'])}
        player_events = {p:set() for p in players}
        for (raw,) in conn.execute('SELECT payload FROM context_contents'):
            budget()
            row = json.loads(raw)
            if row.get('source_schema') not in {STATUS_SCHEMA, SOURCE_SCHEMA}:
                continue
            p = row['payload']
            participants = p['participant_ids'] if row['source_schema'] == STATUS_SCHEMA else (p['player_id'], p['opponent_id'])
            for player in players.intersection(participants):
                player_events[player].add(row['event_key'])
        results = []
        for ref, origin in sample:
            budget()
            event = origin['event']
            keys = {event['event_key']} | player_events[event['home_id']] | player_events[event['away_id']]
            history = []
            for key in sorted(keys):
                for raw in conn.execute(_SELECT+" WHERE r.event_key=? AND r.observed_at<=? AND r.source='espn' AND r.kind IN ('event_status','workload') ORDER BY r.observed_at,r.digest",
                        (key, origin['cutoff'])):
                    budget()
                    row = _decode_receipt(raw)
                    row.update(evidence_class='prospective', effective_at=row['observed_at'], publication_resolution=None)
                    validate_selected_tennis_receipt(row)
                    if row['payload']['tour'] != event['tour']:
                        raise ContextContractError('native event crosses tennis tours')
                    history.append(row)
            history = tuple(sorted(history, key=lambda row: (row['observed_at'], row['digest'])))
            # A content index is only a coarse query aid, not native evidence.
            # Rows actually used above have all passed physical/source checks.
            from tennis.history_projection import PreparedTennisHistory
            owner = PreparedTennisHistory(history)
            with owner.feature_scope(event) as observations:
                features = tennis_features_v4(event, observations, original_base(origin),
                    cutoff=datetime.fromisoformat(origin['cutoff']))
            measured = {}
            for name in ('bounded_sets_1d_delta', 'bounded_sets_3d_delta', 'bounded_games_3d_delta',
                         'bounded_minutes_3d_delta', 'observed_recovery_minimum_hours_delta',
                         'bounded_recovery_minimum_hours_delta'):
                measured[name] = features['values'][name]
            complete = {name: features['values'][name] for name in (
                'bounded_sets_complete_1d_a', 'bounded_sets_complete_1d_b',
                'bounded_sets_complete_3d_a', 'bounded_sets_complete_3d_b')}
            results.append({'event_key':event['event_key'], 'tour':event['tour'], 'original_ref':ref,
                'cutoff':origin['cutoff'], 'references':len(history), 'coverage':features['coverage'],
                'measured':measured, 'complete_observed_subset':complete})
            if progress:
                progress({'phase':'features', 'completed':len(results), 'total':len(sample)})
        return {'schema':1, 'as_of':clock, 'kind':'native-readiness-not-empirical-qualification',
            'original_publications':publications, 'unique_original_events':len(originals),
            'late_original_publications':late, 'matching_final_events':len(matched),
            'outcome_exclusions':dict(exclusions), 'artifact_kinds':kinds, 'sample':results,
            'sample_limited':len(matched)>len(sample), 'sample_policy':'evenly-spaced-earliest-original-time-order',
            'elapsed_seconds':round(monotonic()-started,3),
            'minimum_untouched_test_events':200, 'total_events_meet_test_count_floor_only':len(matched)>=200,
            'qualified':False, 'reason':'inventory_only_no_train_tune_test_improvement_evaluation'}
