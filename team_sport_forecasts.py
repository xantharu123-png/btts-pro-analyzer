"""Immutable same-call research forecasts; no provider or model execution."""
from dataclasses import dataclass, fields
from datetime import datetime, timezone
import math
import re
from types import MappingProxyType
from typing import Mapping
from zoneinfo import ZoneInfo

SOURCE = 'team_sport_research'
SCHEMA = 'team-sport-forecast-v1'
POLICY = 'team-sport-descriptive-v1'
SPORT_NAMES = {'basketball': 'Basketball', 'ice_hockey': 'Eishockey'}
SCOPES = {'basketball': 'including_overtime', 'ice_hockey': 'including_overtime_shootout'}


def _clock(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('forecast clock must be timezone-aware')
    return value.astimezone(timezone.utc)


def _probability(value):
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                             or not math.isfinite(value) or not 0 <= value <= 1):
        raise ValueError('invalid forecast probability')


@dataclass(frozen=True)
class TeamSportForecast:
    schema: str
    sport: str
    provider: str
    provider_event_id: str
    home_id: str
    away_id: str
    home: str
    away: str
    starts_at: datetime
    modeled_at: datetime
    source_observed_at: datetime
    model_version: str
    model_input_hash: str
    p_home: float | None
    p_away: float | None
    market_contract: str
    model_scope: str
    training_games: int
    home_games: int
    away_games: int
    evaluation: Mapping
    latest_result_observed_at: datetime | None
    missing: tuple[str, ...]
    factors: tuple[str, ...]
    limitations: tuple[str, ...]
    kind: str = 'full_match_winner'
    p_home_regulation: float | None = None
    p_draw_regulation: float | None = None

    def __post_init__(self):
        if self.schema != SCHEMA or self.sport not in SPORT_NAMES or self.kind != 'full_match_winner':
            raise ValueError('unsupported forecast schema/sport')
        for name in ('provider', 'provider_event_id', 'home', 'away', 'model_version'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 500:
                raise ValueError('invalid forecast identity')
        if any(not isinstance(getattr(self, name), str) for name in ('home_id', 'away_id')):
            raise ValueError('invalid team identities')
        if self.home.casefold() == self.away.casefold() or (self.home_id and self.home_id == self.away_id):
            raise ValueError('teams must differ')
        if not isinstance(self.model_input_hash, str) or not re.fullmatch('[0-9a-f]{64}', self.model_input_hash):
            raise ValueError('invalid model input hash')
        if self.market_contract != 'match_winner_including_ot' or self.model_scope != SCOPES[self.sport]:
            raise ValueError('invalid full-match contract')
        for name in ('starts_at', 'modeled_at', 'source_observed_at'):
            object.__setattr__(self, name, _clock(getattr(self, name)))
        if not self.source_observed_at <= self.modeled_at <= self.starts_at:
            raise ValueError('invalid forecast chronology')
        if self.latest_result_observed_at is not None:
            object.__setattr__(self, 'latest_result_observed_at', _clock(self.latest_result_observed_at))
            if self.latest_result_observed_at > self.modeled_at:
                raise ValueError('future result observation')
        for name in ('p_home', 'p_away', 'p_home_regulation', 'p_draw_regulation'):
            _probability(getattr(self, name))
        if (self.p_home is None) != (self.p_away is None):
            raise ValueError('probabilities must be jointly available')
        if self.p_home is not None and not math.isclose(self.p_home + self.p_away, 1, rel_tol=0, abs_tol=1e-12):
            raise ValueError('probabilities must complement')
        if (self.p_home_regulation is None) != (self.p_draw_regulation is None):
            raise ValueError('regulation components must be jointly available')
        if self.p_home_regulation is not None and (self.sport != 'ice_hockey' or self.p_home_regulation + self.p_draw_regulation > 1 + 1e-12):
            raise ValueError('invalid regulation components')
        for name in ('training_games', 'home_games', 'away_games'):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError('invalid sample size')
        if max(self.home_games, self.away_games) > self.training_games:
            raise ValueError('team sample exceeds training sample')
        for name in ('missing', 'factors', 'limitations'):
            values = getattr(self, name)
            if not isinstance(values, (tuple, list)) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError('invalid forecast evidence')
            object.__setattr__(self, name, tuple(values))
        evaluation = self.evaluation
        if not isinstance(evaluation, Mapping) or set(evaluation) != {'count', 'brier_score', 'baseline_brier_score', 'log_loss', 'method'}:
            raise ValueError('invalid evaluation schema')
        count = evaluation['count']
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= self.training_games:
            raise ValueError('invalid evaluation count')
        if evaluation['method'] != 'results-observed-before-evaluated-kickoff':
            raise ValueError('invalid evaluation method')
        for name in ('brier_score', 'baseline_brier_score', 'log_loss'):
            value = evaluation[name]
            if (value is None) != (count == 0) or (value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0)):
                raise ValueError('invalid evaluation metric')
        object.__setattr__(self, 'evaluation', MappingProxyType(dict(evaluation)))

    def to_dict(self):
        result = {}
        for field in fields(self):
            value = getattr(self, field.name)
            result[field.name] = value.isoformat() if isinstance(value, datetime) else dict(value) if isinstance(value, Mapping) else list(value) if isinstance(value, tuple) else value
        return result

    @classmethod
    def from_dict(cls, payload):
        if not isinstance(payload, Mapping) or set(payload) != {f.name for f in fields(cls)}:
            raise ValueError('invalid closed forecast schema')
        return cls(**payload)

    def validate_snapshot(self, snapshot):
        from riskobet_domain import stable_event_key
        if (snapshot.event_key != stable_event_key(self.sport, self.provider, self.provider_event_id)
                or snapshot.sport != self.sport or snapshot.event_label != f'{self.home} vs {self.away}'
                or snapshot.starts_at != self.starts_at or snapshot.modeled_at != self.modeled_at
                or snapshot.model_version != self.model_version or self.source_observed_at > snapshot.input_cutoff_at
                or (self.latest_result_observed_at is not None and self.latest_result_observed_at > snapshot.input_cutoff_at)):
            raise ValueError('forecast is not bound to snapshot')


def team_sport_forecast_rows(run, *, now, target_date):
    now = _clock(now)
    result = []
    for snapshot in run.snapshots:
        payload = snapshot.team_sport_forecast
        if payload is None or snapshot.starts_at <= now or snapshot.starts_at.astimezone(ZoneInfo('Europe/Zurich')).date() != target_date:
            continue
        if snapshot.modeled_at > now or payload.source_observed_at > now or not snapshot.factors or any(f.fresh_until < now for f in snapshot.factors):
            continue
        if payload.p_home is None or payload.missing:
            continue
        for side, probability, name in (('home', payload.p_home, payload.home), ('away', payload.p_away, payload.away)):
            key = f'{SOURCE}:{snapshot.snapshot_id}:{side}'
            result.append(dict(key=key, candidate_id=key, source=SOURCE, sport=SPORT_NAMES[payload.sport],
                event=snapshot.event_label, event_identity=snapshot.event_key, label=f'{snapshot.event_label}: {name}',
                market='Sieger inklusive Overtime' if payload.sport == 'basketball' else 'Sieger inklusive Verlängerung und Penaltyschießen',
                market_key='H2H', selection=name, selected_competitor=name,
                competitor_a=payload.home, competitor_b=payload.away, competitor_a_id=payload.home_id, competitor_b_id=payload.away_id,
                provider_event_id=payload.provider_event_id, fixture_source=payload.provider, competition=snapshot.competition,
                probability=probability, probability_haircut=None, minimum_odds=None,
                evidence_stage='RESEARCH', statistical_release_passed=False, policy_version=POLICY,
                model_version=payload.model_version, model_scope=payload.model_scope,
                modeled_at=snapshot.modeled_at.isoformat(), input_cutoff_at=snapshot.input_cutoff_at.isoformat(),
                scheduled_start=snapshot.starts_at.isoformat(), status='PRICE_REQUIRED',
                conservative_probability=None, reference_price_status='UNAVAILABLE',
                detail=f'Sportspezifisches Modell aus {payload.training_games} abgeschlossenen Spielen. Modell noch nicht unabhängig bestätigt.',
                team_sport_snapshot=snapshot.to_dict()))
    return result


def valid_research_row(row, *, now=None):
    """Closed nullable-risk exception bound to a complete immutable snapshot."""
    if not isinstance(row, Mapping) or row.get('source') != SOURCE:
        return False
    if (row.get('evidence_stage') != 'RESEARCH' or row.get('statistical_release_passed') is not False
            or any(row.get(key) is not None for key in ('probability_haircut', 'minimum_odds', 'conservative_probability'))
            or any(key in row for key in ('release_contract', 'release_overlay', 'offered_odds', 'bookmaker_odds', 'n1bet_odds'))):
        return False
    try:
        from riskobet_automation import snapshot_from_dict
        from types import SimpleNamespace
        snapshot = snapshot_from_dict(row.get('team_sport_snapshot'))
        current = _clock(now) if now is not None else snapshot.modeled_at
        expected = team_sport_forecast_rows(SimpleNamespace(snapshots=(snapshot,)), now=current,
            target_date=snapshot.starts_at.astimezone(ZoneInfo('Europe/Zurich')).date())
        for candidate in expected:
            if all(key in row and row[key] == value for key, value in candidate.items() if key not in {'status', 'team_sport_snapshot', 'reference_price_status'}):
                return True
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        pass
    return False


def research_signal_row(signal):
    result = dict(vars(signal))
    snapshot = signal.team_sport_snapshot if isinstance(signal.team_sport_snapshot, Mapping) else {}
    result.update(event=signal.event_label, event_identity=snapshot.get('event_key'),
                  conservative_probability=None, reference_price_status='UNAVAILABLE')
    return result


def team_sport_source_coverage(run, rows, *, now, target_date):
    result = {}
    for sport, label in SPORT_NAMES.items():
        snapshots = [s for s in run.snapshots if s.sport == sport and s.starts_at > now
                     and s.starts_at.astimezone(ZoneInfo('Europe/Zurich')).date() == target_date]
        count = sum(row['sport'] == label for row in rows)
        reasons = []
        for snapshot in snapshots:
            payload = snapshot.team_sport_forecast
            if payload is None:
                reasons.append('legacy_snapshot_without_full_forecast')
            elif payload.p_home is None or payload.missing:
                reasons.append('base_probability_unavailable')
            elif not snapshot.factors or any(f.fresh_until < now for f in snapshot.factors):
                reasons.append('source_evidence_expired')
            elif snapshot.modeled_at > now or payload.source_observed_at > now:
                reasons.append('future_source_clock')
        if not snapshots:
            reasons.append('no_current_snapshot')
        result[sport] = dict(status='research_forecasts' if count else 'research_coverage_missing',
            candidate_count=count, published_model_selection_count=count, published_recommendation_count=0,
            snapshot_count=len(snapshots), coverage_reasons=sorted(set(reasons)), operational_error_count=0,
            reference_quote_count=0, price_checked_count=0)
    return result
