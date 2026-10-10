"""Presentation facts must follow the chosen side and exact consumed history."""
import copy
import importlib
import unittest
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from contextlib import closing


def api(name):
    try:
        return getattr(importlib.import_module('team_customer_facts'), name)
    except (ModuleNotFoundError, AttributeError):
        raise AssertionError('Missing team customer display-facts behavior: ' + name)


class TeamCustomerFactsTests(unittest.TestCase):
    def esports_signal(self):
        return SimpleNamespace(sport='E-Sport', probability=.72,
            competitor_a='Alpha', competitor_b='Beta', selected_competitor='Alpha',
            provider_event_id='55', modeled_at='2026-09-28T10:00:00+00:00',
            context_evidence={'schema': 'esports-card-basis-v1', 'provider_event_id': '55',
                'modeled_at': '2026-09-28T10:00:00+00:00', 'competitor_a': 'Alpha',
                'competitor_b': 'Beta', 'elo_a': 1600., 'elo_b': 1500., 'series_type': 3})

    def test_esports_reason_compares_chosen_side_not_always_first_team(self):
        signal = self.esports_signal()
        signal.selected_competitor = 'Beta'
        signal.probability = .28
        actual = api('team_customer_explanation')(signal)
        self.assertFalse(any('höher' in reason for reason in actual['reasons']))
        self.assertIn('Beta', actual['counterpoint'])
        self.assertIn('längerfristigen Serienergebnisse', actual['counterpoint'])
        self.assertNotIn('Elo', actual['counterpoint'])
        self.assertIn('72,0 %', actual['counterpoint'])

    def test_esports_recent_windows_use_consumed_order_and_do_not_mutate_original(self):
        match = {'id': 55, 'team1': 'Alpha', 'team2': 'Beta',
            'team1_history': [{'won': bool(i % 2)} for i in range(20)],
            'team2_history': [{'won': i < 4} for i in range(20)]}
        original = {'inputs_hash': 'a'*64, 'consumed': {'history_indices': {
            'team1': list(range(19, -1, -1)), 'team2': list(range(20))}}}
        before = copy.deepcopy((match, original))
        facts = api('esports_recent_facts')(match, original)
        self.assertEqual(facts['a_results'][:5], [True, False, True, False, True])
        signal = self.esports_signal()
        signal.context_evidence['recent_results'] = facts
        signal.context_evidence['source_input_hash'] = 'a'*64
        actual = api('team_customer_explanation')(signal)
        self.assertTrue(any('Alpha' in line and '3/5' in line and '5/10' in line for line in actual['recent']))
        self.assertTrue(any('Beta' in line and '4/5' in line and '4/10' in line for line in actual['recent']))
        self.assertEqual((match, original), before)
        self.assertFalse(any('stärk' in line for line in actual['recent']))

    def test_esports_invalid_consumed_position_or_non_boolean_outcome_fails_closed(self):
        match = {'id': 55, 'team1': 'Alpha', 'team2': 'Beta',
            'team1_history': [{'won': True} for _ in range(20)],
            'team2_history': [{'won': False} for _ in range(20)]}
        original = {'inputs_hash': 'a'*64, 'consumed': {'history_indices': {
            'team1': list(range(20)), 'team2': list(range(20))}}}
        original['consumed']['history_indices']['team1'][4] = True
        self.assertIsNone(api('esports_recent_facts')(match, original))
        original['consumed']['history_indices']['team1'][4] = 4
        match['team2_history'][3]['won'] = 1
        self.assertIsNone(api('esports_recent_facts')(match, original))

    def test_esports_recent_evidence_must_match_context_source_hash(self):
        signal = self.esports_signal()
        signal.context_evidence.update(source_input_hash='a'*64, recent_results={
            'schema': 'esports-recent-results-v1', 'provider_event_id': '55',
            'source_input_hash': 'b'*64, 'competitor_a': 'Alpha', 'competitor_b': 'Beta',
            'a_results': [True]*10, 'b_results': [False]*10})
        self.assertEqual(api('team_customer_explanation')(signal)['recent'], ())

    def test_esports_better_last_five_is_a_factual_reason_not_opponent_strength(self):
        signal = self.esports_signal()
        signal.context_evidence.update(source_input_hash='a'*64, recent_results={
            'schema': 'esports-recent-results-v1', 'provider_event_id': '55',
            'source_input_hash': 'a'*64, 'competitor_a': 'Alpha', 'competitor_b': 'Beta',
            'a_results': [True]*5+[False]*5, 'b_results': [False]*5+[True]*5})
        reasons = api('team_customer_explanation')(signal)['reasons']
        self.assertTrue(any('5/5' in reason and '0/5' in reason for reason in reasons))
        self.assertFalse(any('stärkere Gegner' in reason for reason in reasons))

    def test_wrong_event_or_model_clock_cannot_supply_esports_facts(self):
        signal = self.esports_signal()
        for field, value in [('provider_event_id', '56'), ('modeled_at', '2026-09-28T11:00:00+00:00'),
                             ('competitor_a', 'Other')]:
            bad = copy.deepcopy(signal)
            bad.context_evidence[field] = value
            actual = api('team_customer_explanation')(bad)
            self.assertEqual(actual['reasons'], ())
            self.assertEqual(actual['recent'], ())

    def test_basketball_uses_only_bound_saved_model_factors_without_prose_inference(self):
        forecast = {'sport': 'basketball', 'model_version': 'sports-prematch-research-v1',
            'provider_event_id': 'event1', 'modeled_at': '2026-09-28T10:00:00+00:00',
            'home': 'Alpha', 'away': 'Beta', 'p_home': .7, 'p_away': .3,
            'factors': ['Gegnerbereinigte erwartete Punktedifferenz Heim–Gast: 8.25; einschließlich Overtime.',
                'Aus den Punktedifferenzen geschätzte Streuung: 12.40 Punkte.'], 'missing': []}
        signal = SimpleNamespace(sport='Basketball', probability=.7, competitor_a='Alpha',
            competitor_b='Beta', selected_competitor='Alpha', provider_event_id='event1',
            modeled_at='2026-09-28T10:00:00+00:00',
            team_sport_snapshot={'team_sport_forecast': forecast})
        actual = api('team_customer_explanation')(signal)
        self.assertEqual(actual['reasons'], tuple(forecast['factors']))
        self.assertIn('30,0 %', actual['counterpoint'])
        self.assertEqual(actual['recent'], ())
        signal.team_sport_snapshot['team_sport_forecast']['provider_event_id'] = 'other'
        self.assertEqual(api('team_customer_explanation')(signal)['reasons'], ())

    def test_hockey_preserves_regulation_scope_and_cricket_is_excluded(self):
        forecast = {'sport': 'ice_hockey', 'model_version': 'sports-prematch-research-v1',
            'provider_event_id': 'event1', 'modeled_at': '2026-09-28T10:00:00+00:00',
            'home': 'Alpha', 'away': 'Beta', 'p_home': .62, 'p_away': .38,
            'factors': ['Erwartete Tore in regulärer Spielzeit: 3.10/2.20.',
                'Verlängerung/Shootout separat aus 14 passenden Spielen berücksichtigt.'], 'missing': []}
        signal = SimpleNamespace(sport='Eishockey', probability=.62, competitor_a='Alpha',
            competitor_b='Beta', selected_competitor='Alpha', provider_event_id='event1',
            modeled_at='2026-09-28T10:00:00+00:00',
            team_sport_snapshot={'team_sport_forecast': forecast})
        actual = api('team_customer_explanation')(signal)
        self.assertIn('regulärer Spielzeit', actual['reasons'][0])
        signal.sport = 'Cricket'
        self.assertEqual(api('team_customer_explanation')(signal), {'reasons': (), 'counterpoint': None, 'recent': ()})

    def hockey_signal(self, *, selected='BOS', goals='3.09/2.60'):
        forecast = {'sport': 'ice_hockey', 'model_version': 'sports-prematch-research-v1',
            'provider_event_id': '2026020070', 'modeled_at': '2026-10-10T02:12:48+00:00',
            'home': 'BOS', 'away': 'PHI', 'p_home': .577, 'p_away': .423,
            'factors': [f'Erwartete Tore in regulärer Spielzeit: {goals}.',
                'Verlängerung/Shootout separat aus 298 passenden Spielen berücksichtigt.'],
            'missing': []}
        return SimpleNamespace(sport='Eishockey', probability=.577 if selected == 'BOS' else .423,
            competitor_a='BOS', competitor_b='PHI', competitor_a_id='6', competitor_b_id='4',
            selected_competitor=selected, fixture_source='NHL', competition='NHL',
            provider_event_id='2026020070', modeled_at=forecast['modeled_at'],
            team_sport_snapshot={'team_sport_forecast': forecast})

    def test_hockey_reason_labels_both_goal_estimates_and_explains_chosen_advantage(self):
        signal = self.hockey_signal()
        before = copy.deepcopy(vars(signal))
        actual = api('team_customer_explanation')(signal)
        reason = actual['reasons'][0]
        self.assertIn('Boston Bruins', reason)
        self.assertIn('Philadelphia Flyers', reason)
        self.assertIn('3,09', reason)
        self.assertIn('2,60', reason)
        self.assertIn('vor', reason)
        self.assertIn('regulärer Spielzeit', reason)
        self.assertNotIn('3.09/2.60', reason)
        self.assertIn('Philadelphia Flyers', actual['counterpoint'])
        self.assertIn('42,3 %', actual['counterpoint'])
        self.assertEqual(vars(signal), before)

    def test_hockey_opposite_side_cannot_inherit_the_home_teams_supporting_reason(self):
        actual = api('team_customer_explanation')(self.hockey_signal(selected='PHI'))
        reason = actual['reasons'][0]
        self.assertIn('Philadelphia Flyers', reason)
        self.assertIn('hinter', reason)
        self.assertNotIn('spricht für Philadelphia', reason)
        self.assertIn('Boston Bruins', actual['counterpoint'])
        self.assertIn('57,7 %', actual['counterpoint'])

    def test_hockey_equal_goal_estimates_do_not_claim_a_goal_advantage(self):
        actual = api('team_customer_explanation')(self.hockey_signal(goals='2.80/2.80'))
        self.assertIn('gleichauf', actual['reasons'][0])
        self.assertNotIn('vor Philadelphia', actual['reasons'][0])

    def test_hockey_malformed_goal_factor_does_not_become_a_supporting_fact(self):
        for goals in ('nan/2.60', '-3.09/2.60', '3.09/2.60 EXTRA', '300.00/2.60'):
            with self.subTest(goals=goals):
                actual = api('team_customer_explanation')(self.hockey_signal(goals=goals))
                self.assertEqual(actual['reasons'], ())

    def test_hockey_wrong_model_binding_cannot_supply_goal_explanation(self):
        signal = self.hockey_signal()
        signal.team_sport_snapshot['team_sport_forecast']['provider_event_id'] = 'wrong'
        self.assertEqual(api('team_customer_explanation')(signal)['reasons'], ())

    def test_team_sidecar_keeps_real_final_scores_and_not_normalized_hockey_ties(self):
        now = datetime(2026, 9, 28, 10, tzinfo=timezone.utc)
        start = now - timedelta(days=1)
        observed = start + timedelta(hours=4)
        original = SimpleNamespace(sport='ice_hockey', as_of=now, input_hash='b'*64,
            raw_event={'provider_event_id': 'future', 'home_team': 'Alpha', 'away_team': 'Beta'},
            identity=SimpleNamespace(event_id='future', home='id:1', away='id:2'),
            matches=(SimpleNamespace(event_id='old', start=start, observed=observed,
                home='id:1', away='id:3', winner_home=1, home_score=2, away_score=2, extra_time=True),),
            raw_history=({'provider_event_id': 'old', 'start_time': start.isoformat(),
                'result_observed_at': observed.isoformat(), 'home_team': 'Alpha', 'away_team': 'Gamma',
                'home_team_id': '1', 'away_team_id': '3', 'home_score': 3, 'away_score': 2,
                'last_period_type': 'OT'},))
        facts = api('team_recent_facts')(original)
        self.assertEqual(facts['a_results'][0]['score'], '3:2')
        self.assertEqual(facts['a_results'][0]['scope'], 'final_including_ot_so')
        self.assertEqual(facts['a_results'][0]['opponent'], 'Gamma')
        self.assertTrue(facts['a_results'][0]['won'])
        self.assertEqual(facts['source_input_hash'], 'b'*64)
        self.assertEqual(facts['b_results'], [])

    def test_team_recent_sidecar_from_actual_capture_keeps_prediction_unchanged(self):
        from sports_prematch import predict_prematch
        from tests.test_sports_prematch import event, history, NOW
        rows = history('ice_hockey')
        normal = predict_prematch('ice_hockey', event('ice_hockey'), rows, NOW)
        captures = []
        captured = predict_prematch('ice_hockey', event('ice_hockey'), rows, NOW, original_capture=captures.append)
        self.assertEqual(captured, normal)
        before = copy.deepcopy(rows)
        facts = api('team_recent_facts')(captures[0])
        self.assertEqual(rows, before)
        self.assertEqual(facts['source_input_hash'], normal.input_hash)
        self.assertEqual(len(facts['a_results']), 10)
        self.assertEqual(len(facts['b_results']), 10)
        self.assertTrue(all(row['score'] and row['opponent'] for row in facts['a_results']))

    def test_team_recent_display_requires_same_original_input_hash(self):
        signal = SimpleNamespace(sport='Basketball', probability=.7, competitor_a='Alpha',
            competitor_b='Beta', selected_competitor='Alpha', provider_event_id='event1',
            modeled_at='2026-09-28T10:00:00+00:00', team_sport_snapshot={'team_sport_forecast': {
            'sport': 'basketball', 'model_version': 'sports-prematch-research-v1',
            'provider_event_id': 'event1', 'modeled_at': '2026-09-28T10:00:00+00:00',
            'home': 'Alpha', 'away': 'Beta', 'p_home': .7, 'p_away': .3, 'model_input_hash': 'a'*64,
            'missing': [], 'factors': []}})
        facts = {'schema': 'team-recent-results-v1', 'sport': 'basketball', 'provider_event_id': 'event1',
            'modeled_at': signal.modeled_at, 'source_input_hash': 'a'*64,
            'competitor_a': 'Alpha', 'competitor_b': 'Beta',
            'a_results': [{'won': True, 'score': '100:90', 'opponent': 'Gamma'}]*10,
            'b_results': [{'won': False, 'score': '90:100', 'opponent': 'Gamma'}]*10}
        good = api('team_customer_explanation')(signal, recent_facts=facts)
        self.assertTrue(any('10/10' in row and '100:90 gegen Gamma' in row for row in good['recent']))
        signal.selected_competitor = 'Beta'
        signal.probability = .3
        weaker = api('team_customer_explanation')(signal, recent_facts=facts)
        self.assertIn('Alpha: 5/5', weaker['counterpoint'])
        facts['source_input_hash'] = 'b'*64
        self.assertEqual(api('team_customer_explanation')(signal, recent_facts=facts)['recent'], ())

    def test_malformed_esports_recent_rows_do_not_crash_or_supply_a_partial_comparison(self):
        signal = self.esports_signal()
        signal.context_evidence.update(source_input_hash='a'*64, recent_results={
            'schema': 'esports-recent-results-v1', 'provider_event_id': '55',
            'source_input_hash': 'a'*64, 'competitor_a': 'Alpha', 'competitor_b': 'Beta',
            'a_results': [True]*10, 'b_results': [None]*10})
        self.assertEqual(api('team_customer_explanation')(signal)['recent'], ())

    def test_esports_source_transports_first_observation_recent_windows_only(self):
        from esports_shadow import EsportsShadowLog
        from ev_signal_sources import esports_signals
        from tests.test_esports_shadow import _match
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / 'shadow.db'
            log = EsportsShadowLog(db)
            self.assertEqual(log.log_predictions([_match()]), 1)
            signal = esports_signals(db, require_released=False)[0]
            facts = signal.context_evidence.get('recent_results')
            self.assertIsNotNone(facts)
            self.assertEqual(facts['a_results'], [True, True, False, True, True, True, False, True, True, True])
            self.assertEqual(facts['b_results'], [False, True, False, False, True, False, True, False, False, True])
            self.assertEqual(log.log_predictions([_match(team1_wins=6, team2_wins=14)]), 0)
            later = esports_signals(db, require_released=False)[0]
            self.assertEqual(later.context_evidence['recent_results'], facts)
            self.assertEqual(later.probability, signal.probability)
            self.assertEqual(later.minimum_odds, signal.minimum_odds)
            with closing(sqlite3.connect(db)) as connection:
                connection.execute("UPDATE esports_shadow_customer_facts SET source_input_hash=?", ('f'*64,))
                connection.commit()
            self.assertNotIn('recent_results', esports_signals(db, require_released=False)[0].context_evidence)

    def test_esports_source_rejects_sidecar_logged_at_mismatch_without_losing_forecast(self):
        from esports_shadow import EsportsShadowLog
        from ev_signal_sources import esports_signals
        from tests.test_esports_shadow import _match
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / 'shadow.db'
            log = EsportsShadowLog(db)
            log.log_predictions([_match()])
            with closing(sqlite3.connect(db)) as connection:
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertIn('esports_shadow_customer_facts', tables)
                connection.execute("UPDATE esports_shadow_customer_facts SET logged_at='2026-09-29T10:00:00+00:00'")
                connection.commit()
            signal = esports_signals(db, require_released=False)[0]
            self.assertNotIn('recent_results', signal.context_evidence)
