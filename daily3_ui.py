"""Flat, manually confirmed real-stake Daily3 UI; no new scanner or timer."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import sqlite3
import uuid
from zoneinfo import ZoneInfo

from account_identity import AccountScopeUnavailable, storage_scope
from betting_math import MINIMUM_RECOMMENDED_DECIMAL_ODDS
from daily3_math import Daily3Error, decimal_odds, format_chf, parse_chf
from daily3_identity import event_guard
from daily3_selection import MIN_MODEL_PROBABILITY, daily3_choices, reservation_minimum_enforced
from daily3_schedule import pending_ready_at, planning_allowance
from daily3_store import Daily3Store, day_balance, expected_return_cents, payout_needs_confirmation
from forecast_compact import render_compact_analysis_html
from runtime_paths import RUNTIME_STATE_DIR
from tip_display_order import ordered_event_rows
from wettfinder_surface import build_wettfinder_card, format_probability

_TZ = ZoneInfo('Europe/Zurich')


def _odds_text(value):
    return '–' if value is None else f'{float(value):.2f}'.replace('.', ',')


def _reservation_block_reason(choice):
    """Why real money may not be reserved on this choice right now ('' = allowed)."""
    if not reservation_minimum_enforced():
        return ''
    if choice.minimum_odds is None:
        return 'Für diese Auswahl liegt keine belastbare Mindestquote vor. Keine Vormerkung.'
    if choice.price_blocked:
        return (f'Die zuletzt beobachtete Quote {_odds_text(choice.offer_odds)} liegt unter der Mindestquote '
                f'{_odds_text(choice.minimum_odds)} dieser Auswahl. Zu diesem Preis keine Vormerkung; die '
                'Prognose bleibt sichtbar. Nach Spielbeginn wird die Tagesfolge neu geplant.')
    return ''


def _require_reservation_price(choice, entered):
    """Real money needs the choice's own minimum; the global 1,20 floor stays in the store."""
    reason = _reservation_block_reason(choice)
    if reason:
        raise Daily3Error(reason)
    if not reservation_minimum_enforced():
        return
    odds = Decimal(decimal_odds(entered))
    if Decimal(str(MINIMUM_RECOMMENDED_DECIMAL_ODDS)) <= odds < Decimal(f'{choice.minimum_odds:.2f}'):
        raise Daily3Error(f'Die angegebene Quote {_odds_text(odds)} liegt unter der Mindestquote '
                          f'{_odds_text(choice.minimum_odds)} dieser Auswahl. Keine Vormerkung.')


def _token(st, key):
    name = '_daily3_action:'+key
    if name not in st.session_state:
        st.session_state[name] = uuid.uuid4().hex
    return st.session_state[name]


def _submit(st, store, scope, key, kind, day, build_args):
    """Run as a widget callback, before the next render reads its snapshot."""
    try:
        from customer_access import enabled, assert_current_scope
        if enabled():
            assert_current_scope(st.context.cookies, scope, "daily3")
        store.command(scope, action_id=_token(st, key), kind=kind, day=day() if callable(day) else day, **build_args())
    except Daily3Error as exc:
        st.session_state['_daily3_notice'] = ('error', str(exc))
    except (OSError, sqlite3.Error):
        st.session_state['_daily3_notice'] = ('error', 'Die Bestätigung konnte nicht gespeichert werden. Bitte neu laden und den gespeicherten Stand prüfen.')
    except (ValueError, TypeError):
        st.session_state['_daily3_notice'] = ('error', 'Bitte die eingegebenen Beträge und Zeitangaben prüfen.')


def _confirmed(st, key, message):
    if st.session_state.get(key) is not True:
        raise Daily3Error(message)


def _callback(st, store, scope, key, kind, day, build_args):
    return dict(on_click=_submit, args=(st, store, scope, key, kind, day, build_args))


def _money_input(st, label, key):
    return st.text_input(label, value='', placeholder='z. B. 10,00', key=key)


def _adjustment_key(key, returned):
    # A second approval covers this exact credit, bet and revision only.
    return key+':'+str(returned)


def _adjustment_fields(st, bet, value_key, key):
    try:
        returned = parse_chf(st.session_state.get(value_key, ''))
    except Daily3Error:
        return
    if not payout_needs_confirmation(bet, returned):
        return
    bound = _adjustment_key(key, returned)
    st.warning(f'Die Gutschrift liegt über dem normalen Rückfluss von {format_chf(expected_return_cents(bet))}. '
               'Bitte Betrag und Quote auf einen Tippfehler prüfen. Eine echte Sondergutschrift braucht eine zweite Bestätigung mit konkretem Grund.')
    st.checkbox('Ich bestätige zusätzlich: Genau dieser höhere Betrag wurde tatsächlich vom Buchmacher gutgeschrieben.', key='adjusted-confirm:'+bound)
    st.text_input('Konkreter Grund der höheren Buchmacher-Gutschrift', max_chars=500, key='adjusted-reason:'+bound)


def _payout_args(st, bet, value_key, key):
    returned = parse_chf(st.session_state[value_key])
    result = dict(returned_cents=returned)
    if payout_needs_confirmation(bet, returned):
        bound = _adjustment_key(key, returned)
        _confirmed(st, 'adjusted-confirm:'+bound, 'Für diese höhere Gutschrift ist eine ausdrückliche Zweitbestätigung erforderlich.')
        result.update(adjustment_confirmed=True, adjustment_reason=st.session_state.get('adjusted-reason:'+bound, ''))
    return result


def _saved_bet(st, store, scope, day, bet):
    snap, revision = bet['snapshot'], bet['revision']
    key = f'{day}:{bet["id"]}:{revision}'
    status = {'reserved': 'Vorgemerkt – noch nicht als platziert bestätigt', 'open': 'Platziert · Ergebnis offen',
              'settled': 'Abgerechnet · vom Nutzer bestätigt', 'cancelled': 'Nicht platziert · Vormerkung verworfen'}[bet['status']]
    with st.container(border=True):
        st.subheader(snap['event_label'])
        st.write(f'{snap["market"]} · {snap["selection"]}')
        st.write(f'{format_chf(bet["stake_cents"])} Einsatz · angenommene Quote {bet["odds"]}')
        st.caption(status)
        # The signed bet snapshot retains its original model notes internally.
        # A saved bet needs its selection and money status, not method prose.
        if bet['external_deviation']:
            st.warning('Nachträglich erfasste externe Wette. Die App dokumentiert diesen Einsatz nur.')
        if bet['under_review']:
            st.warning('Abrechnung wird geklärt. Bis dahin keine neue Einsatzvormerkung.')
        if bet['status'] == 'reserved':
            with st.form('d3-place:'+key):
                st.text_input('Buchmacher / Belegnummer', key='ref:'+key)
                st.checkbox('Diese Wette ist mit genau diesem Einsatz, Markt und dieser Quote beim Buchmacher platziert.', key='placed:'+key)
                def place_args():
                    _confirmed(st, 'placed:'+key, 'Bitte die tatsächliche Platzierung bestätigen.')
                    return dict(bet_id=bet['id'], revision=revision, reference=st.session_state['ref:'+key])
                st.form_submit_button('Als platziert bestätigen', **_callback(st, store, scope, 'place:'+key, 'place', day, place_args))
            with st.form('d3-cancel:'+key):
                st.checkbox('Ich habe diese Wette nicht platziert.', key='not-placed:'+key)
                st.form_submit_button('Vormerkung verwerfen', **_callback(st, store, scope, 'cancel:'+key, 'cancel', day,
                    lambda: dict(bet_id=bet['id'], revision=revision, not_placed=st.session_state['not-placed:'+key])))
        elif bet['status'] == 'open':
            with st.form('d3-settle:'+key):
                _money_input(st, 'Tatsächlich gutgeschriebener Gesamtbetrag in CHF', 'returned:'+key)
                st.caption('Inklusive zurückgezahltem Einsatz, nach Gebühren. Bei Verlust 0; bei vollständiger Stornierung den erstatteten Einsatz. Keine erwartete Auszahlung eintragen.')
                st.text_input('Abrechnungsbeleg / Buchmacher', key='settled-ref:'+key)
                st.checkbox('Der Buchmacher hat endgültig abgerechnet und diesen Betrag gutgeschrieben.', key='settled-confirm:'+key)
                _adjustment_fields(st, bet, 'returned:'+key, 'settle:'+key)
                def settle_args():
                    _confirmed(st, 'settled-confirm:'+key, 'Bitte die tatsächliche Abrechnung bestätigen.')
                    return dict(bet_id=bet['id'], revision=revision, reference=st.session_state['settled-ref:'+key],
                                **_payout_args(st, bet, 'returned:'+key, 'settle:'+key))
                st.form_submit_button('Abrechnung bestätigen', **_callback(st, store, scope, 'settle:'+key, 'settle', day, settle_args))
        elif bet['status'] == 'settled':
            st.write(f'Rückzahlung: {format_chf(bet["returned_cents"])} · Netto: {format_chf(bet["returned_cents"]-bet["stake_cents"])}')
            with st.expander('Abrechnungsbeleg und Korrektur'):
                st.write(bet['reference'])
                with st.form('d3-correct:'+key):
                    _money_input(st, 'Korrigierter, tatsächlich gutgeschriebener Gesamtbetrag in CHF', 'correction:'+key)
                    st.text_input('Neuer Abrechnungsbeleg', key='corrected-ref:'+key)
                    st.text_input('Grund der Korrektur', key='corrected-reason:'+key)
                    st.checkbox('Die korrigierte Buchmacherabrechnung ist abgeschlossen.', key='corrected-confirm:'+key)
                    _adjustment_fields(st, bet, 'correction:'+key, 'correct:'+key)
                    def correct_args():
                        _confirmed(st, 'corrected-confirm:'+key, 'Bitte die tatsächliche korrigierte Abrechnung bestätigen.')
                        return dict(bet_id=bet['id'], revision=revision, reference=st.session_state['corrected-ref:'+key],
                                    reason=st.session_state['corrected-reason:'+key],
                                    **_payout_args(st, bet, 'correction:'+key, 'correct:'+key))
                    st.form_submit_button('Korrektur nachvollziehbar speichern', **_callback(st, store, scope, 'correct:'+key, 'correct', day, correct_args))
        if bet['status'] in ('open', 'settled') and not bet['under_review']:
            with st.expander('Abrechnung noch ungeklärt?'):
                with st.form('d3-review:'+key):
                    st.text_input('Was wird noch geklärt?', key='review-reason:'+key)
                    st.form_submit_button('Als ungeklärt markieren', **_callback(st, store, scope, 'review:'+key, 'review', day,
                        lambda: dict(bet_id=bet['id'], revision=revision, reason=st.session_state['review-reason:'+key])))


def _external_bet(st, store, scope, history, today, now):
    """Truthful outside-limit entry, visibly NOT another authorized bet slot."""
    if not history:
        return
    with st.expander('Bereits extern platzierte Wette nachtragen'):
        st.warning('Nur bereits getätigte Wetten nachtragen. Eine Überschreitung des gewählten Tagesbudgets wird angezeigt.')
        with st.form('d3-external:'+scope):
            st.selectbox('Zugehöriger Tageslauf', sorted(history, reverse=True), key='d3-ext-day')
            sports = {'Fußball': 'football', 'Tennis': 'tennis', 'Basketball': 'basketball', 'Eishockey': 'hockey', 'E-Sport': 'esports'}
            st.selectbox('Sport der externen Wette', list(sports), key='d3-ext-sport')
            st.text_input('Spiel / beide Teilnehmer', key='d3-ext-event')
            local_now = now.astimezone(_TZ)
            st.date_input('Spieltag', value=local_now.date(), key='d3-ext-date')
            st.time_input('Spielbeginn', value=local_now.time().replace(second=0, microsecond=0), step=60, key='d3-ext-time')
            st.selectbox('Zeitzone', ['Schweizer Zeit', 'UTC'], key='d3-ext-zone')
            st.text_input('Exakter Markt, Linie und Spielzeitraum', key='d3-ext-market')
            st.text_input('Tatsächlich gewettete Auswahl', key='d3-ext-selection')
            _money_input(st, 'Tatsächlicher Einsatz in CHF', 'd3-external-stake')
            st.text_input('Tatsächlich angenommene Quote', value='', key='d3-ext-odds')
            st.text_input('Buchmacher und Belegnummer', key='d3-ext-reference')
            st.text_input('Warum wird die Wette nachgetragen?', key='d3-ext-reason')
            st.checkbox('Diese Wette ist bereits platziert. Ich beantrage keinen weiteren Einsatz.', key='d3-ext-confirm')
            key = f'external:{scope}:{sum(len(d["bets"]) for d in history.values())}'
            def external_args():
                _confirmed(st, 'd3-ext-confirm', 'Bitte nur eine tatsächlich platzierte Wette nachtragen.')
                values = st.session_state
                start = _external_start(values['d3-ext-date'], values['d3-ext-time'], values['d3-ext-zone'])
                sport, event = sports[values['d3-ext-sport']], values['d3-ext-event']
                native = hashlib.sha256(json.dumps([sport, event.strip(), start.isoformat()]).encode()).hexdigest()
                snap = dict(event_id='external:'+native, sport=sport, event_label=event,
                    market_key='EXTERNAL_EXACT', market=values['d3-ext-market'], selection=values['d3-ext-selection'], scheduled_start=start.isoformat(),
                    signal_key='external:'+native, model_probability=None, modeled_at=None, model_version=None,
                    analysis_basis='Extern erfasste Buchmacherwette; keine Modellauswahl der App.',
                    analysis_caution='Für diesen Nachtrag wird keine Modellwahrscheinlichkeit oder Qualität behauptet.',
                    policy_version='external-bookmaker-record-v1')
                snap['event_guard'] = dict(event_guard(dict(sport=sport, event_label=event, scheduled_start=start.isoformat())),
                                           identity=snap['event_id'])
                return dict(bet_id=_token(st, 'bet:'+key), snapshot=snap,
                            stake_cents=parse_chf(values['d3-external-stake'], positive=True), odds=decimal_odds(values['d3-ext-odds']),
                            reference=values['d3-ext-reference'], reason=values['d3-ext-reason'])
            st.form_submit_button('Reale externe Wette nachtragen', **_callback(st, store, scope, key, 'external',
                lambda: st.session_state['d3-ext-day'], external_args))


def _external_start(day, clock, zone):
    """Resolve a wall clock without guessing in Zurich's skipped/repeated hour."""
    if zone not in ('Schweizer Zeit', 'UTC'):
        raise Daily3Error('Bitte eine gültige Zeitzone wählen.')
    wall = datetime.combine(day, clock).replace(tzinfo=None)
    if zone == 'UTC':
        return wall.replace(tzinfo=timezone.utc)
    first = wall.replace(tzinfo=_TZ, fold=0)
    second = wall.replace(tzinfo=_TZ, fold=1)
    if first.utcoffset() != second.utcoffset():
        raise Daily3Error('Diese Schweizer Uhrzeit ist wegen der Zeitumstellung nicht eindeutig. Bitte den Spielbeginn in UTC eintragen.')
    return first


def render_daily3(st, *, snapshot_loader=None, store_factory=None, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(_TZ).date().isoformat()
    st.header('3 a day keeps the job away')
    notice = st.session_state.pop('_daily3_notice', None)
    if notice:
        st.error(notice[1])
    st.caption('CHF 50 Tagesbudget · bis zu 3 Einzelwetten · Ziel +CHF 150, nicht garantiert')
    with st.popover('Auswahl & Regeln'):
        st.write(f'Mindestens {MIN_MODEL_PROBABILITY:.0%} in allen drei belegten Modellvarianten. Eine Auswahl pro Spiel; keine pauschalen Wettartenverbote. Ein positiver Form- oder Belagbonus ist keine Voraussetzung.')
        st.write('Die früheste passende Auswahl beginnt die Tagesfolge. Bei gleichem Spielbeginn hat das geringere modellierte Verlustrisiko Vorrang; danach folgen Vielfalt und Formsignal.')
        st.write('Planungsabstand: 3 Stunden für Fußball, Basketball und Eishockey; 4 Stunden für Tennis und E-Sport. Das sind Zeitpuffer, keine garantierten Spiel- oder Abrechnungszeiten. Die nächste Wette wird erst nach tatsächlicher Abrechnung verfügbar.')
        st.write('Fußball: Formvergleich. ATP-Tennis: Vergleich mit und ohne Belaggewichtung, mit ausreichender Spielerhistorie. Keine unabhängigen Zweitmodelle. Für weitere Sportarten fehlen noch qualifizierte Vergleiche; ihre normalen Prognosen bleiben sichtbar.')
        st.write('Diese Auswahl nutzt den Prognosepool des Wettfinders, aber eine eigene Auswahlregel. Sie ist keine unabhängige Zweitbestätigung und keine nachgewiesene Sicherheitsrangliste. Fehlende Kontextdaten bleiben am Spiel sichtbar.')
        st.write('Die Auswahlen entstehen ohne Buchmacherquote. Für eine tatsächliche Vormerkung gilt die Mindestquote der jeweiligen Auswahl, mindestens 1,20: der Preis, ab dem die vorsichtige Modellrechnung (Modellwahrscheinlichkeit abzüglich Unsicherheitsabschlag) 3 % Risiko-Erwartungswert erreicht. Sie ist keine erwartete Buchmacherquote. Das CHF-150-Ziel verändert die Auswahl nicht; drei passende Auswahlen sind nicht täglich verfügbar.')
        st.write('Maximal CHF 50 eigene Mittel pro Tag, kein Nachschuss. Nur endgültig abgerechnete Rückzahlungen werden wieder verfügbar. Verfügbar ist eine Obergrenze, keine Einsatzempfehlung. Auch Gewinne können wieder verloren gehen.')
        st.write('Echte Wetten werden manuell erfasst; keine Buchmacheranbindung. Das Limit gilt nur für diesen Browserbereich, nicht für externe Wetten oder spätere Buchmacherkorrekturen. Wetten sind kein verlässliches Einkommen.')
    if snapshot_loader is None:
        from ev_signal_sources import automated_wettfinder_snapshot
        snapshot_loader = automated_wettfinder_snapshot
    snapshot = snapshot_loader(now=now)  # One persisted artifact, no model/API rerun.
    try:
        scope = storage_scope(st.session_state)
    except AccountScopeUnavailable:
        st.info('Kontozuordnung lädt. Auswahlen sind sichtbar; Einsätze danach verfügbar.')
        scope = None
    store, history, storage_ready = None, {}, False
    if scope:
        try:
            store = (store_factory or (lambda: Daily3Store(RUNTIME_STATE_DIR/'daily3.db')))()
            history = store.history(scope)
            storage_ready = True
        except Daily3Error as exc:
            st.error(str(exc))
        except (OSError, sqlite3.Error, RuntimeError):
            st.error('Die Tagesaufzeichnungen sind momentan nicht verfügbar. Das verbleibende Budget kann nicht zuverlässig berechnet werden.')
    day = history.get(today)
    prior_pending = [d for d in history.values() if d['date'] != today and
                     any(b['status'] in ('reserved', 'open') or b['under_review'] for b in d['bets'].values())]
    if prior_pending:
        st.warning('Noch Wetten oder Abrechnungen vom Vortag offen. Erst danach kann ein neues Tagesbudget beginnen.')
    if day:
        state = day_balance(day)
        st.subheader(f'Dein Tag · {datetime.fromisoformat(today).strftime("%d.%m.%Y")}')
        for labels in ((('Eigenbudget', format_chf(5000)), ('Verfügbar', format_chf(state.available_cents))),
                       (('Offen / vorgemerkt', format_chf(state.open_cents+state.reserved_cents)), ('Netto abgerechnet', format_chf(state.realised_cents)))):
            columns = st.columns(2)
            for column, (label, value) in zip(columns, labels):
                column.metric(label, value)
        st.caption(f'{state.used_slots}/3 Wetten erfasst · Verfügbar ist keine Einsatzempfehlung.')
        if state.available_cents < 0:
            st.warning('Die tatsächlichen Buchungen überschreiten das Budget. Keine weiteren Vormerkungen; es wird nichts künstlich ausgeglichen.')
        if state.closed:
            st.info('Für heute beendet. Offene Wetten und Abrechnungen bleiben erhalten.')
        else:
            st.button('Für heute beenden', key='d3-close:'+scope+today,
                      **_callback(st, store, scope, 'close:'+scope+today, 'close', today, dict))
    else:
        if storage_ready and not prior_pending:
            st.button('CHF 50 Tagesbudget bestätigen', key='d3-start:'+scope+today,
                      **_callback(st, store, scope, 'start:'+scope+today, 'start', today, dict))
    occupied = {b['event_id'] for b in day['bets'].values() if b['status'] != 'cancelled'} if day else set()
    occupied_guards = [b['snapshot']['event_guard'] for b in day['bets'].values() if b['status'] != 'cancelled'] if day else []
    used = day_balance(day).used_slots if day else 0
    bets = list(day['bets'].values()) if day else []
    pending = any(b['status'] in ('reserved', 'open') or b['under_review'] for b in bets)
    choices = daily3_choices(snapshot.forecasts, now=now, occupied_events=occupied, occupied_guards=occupied_guards,
                             used_slots=used, not_before=pending_ready_at(bets, now=now))
    if choices:
        noun = 'Auswahl' if len(choices) == 1 else 'Auswahlen'
        st.subheader(f'{len(choices)} defensive Modell-{noun}')
    elif used < 3:
        st.info('Heute keine passende Daily3-Auswahl. Weitere Spiele findest du im Wettfinder.')
    if pending:
        st.caption('Nächste Wette erst nach Abrechnung der aktuellen Wette.')
    can_reserve = (storage_ready and day is not None and not day['closed'] and not prior_pending
                   and not pending and day_balance(day).available_cents > 0)
    with st.container(key='daily3_choices_layout'):
        choice_panels = st.columns(len(choices)) if choices else []
    # Sort only presentation. Original chronological slots still own the next
    # reservation, validation and ready-role; later legs never gain authority.
    display_choices = ordered_event_rows(enumerate(choices),
        event_key=lambda item: item[1].event_id, starts_at=lambda item: item[1].start,
        probability=lambda item: item[1].signal.probability)
    for display_index, (index, choice) in enumerate(display_choices):
        snap = choice.snapshot()
        # Only a changed model selection invalidates an unsubmitted form.
        fingerprint = hashlib.sha256(json.dumps(snap, sort_keys=True).encode()).hexdigest()
        key = f'{scope}:{today}:{choice.signal.key}:{len(day["bets"]) if day else 0}:{fingerprint}'
        with choice_panels[display_index].container(border=True):
            st.caption(f'Wette {used+index+1} · {choice.start.astimezone(_TZ):%H:%M} · Planungsabstand {int(planning_allowance(choice.sport).total_seconds()/3600)} Std.')
            from wettfinder_surface import render_editorial_card_html
            from wettfinder_identity import rendered_identity_card
            card = build_wettfinder_card(choice.signal, quote=choice.signal.reference_quote, now=now)
            card = rendered_identity_card(card, choice.signal)
            st.markdown(render_editorial_card_html(card,
                supporting_fact=choice.comparison.summary), unsafe_allow_html=True)
            block_reason = _reservation_block_reason(choice)
            if block_reason:
                st.warning(block_reason)
            elif reservation_minimum_enforced():
                st.caption(f'Mindestquote für diese Auswahl: {_odds_text(choice.minimum_odds)} · zuletzt beobachtet '
                           f'{_odds_text(choice.offer_odds)}. Preis, ab dem die vorsichtige Modellrechnung 3 % '
                           'Risiko-Erwartungswert erreicht; keine erwartete Buchmacherquote.')
            else:
                st.caption(f'Deine Mindestquote für eine tatsächliche Wette: 1,20 · rechnerische Mindestquote dieser '
                           f'Auswahl {_odds_text(choice.minimum_odds)} · zuletzt beobachtet {_odds_text(choice.offer_odds)}. '
                           'Die rechnerische Mindestquote ist eine Information, keine Sperre.')
            if can_reserve and index == 0 and not block_reason:
                with st.form('d3-reserve:'+key):
                    _money_input(st, 'Eigener Einsatz in CHF', 'stake:'+key)
                    st.text_input('Tatsächlich angebotene Dezimalquote', value='', placeholder='z. B. 1,95', key='odds:'+key)
                    st.checkbox('Spiel, Auswahl, Linie und Spielzeitraum stimmen beim Buchmacher exakt überein.', key='exact:'+key)
                    def reserve_args(key=key, snap=snap, fingerprint=fingerprint, signal_key=choice.signal.key):
                        _confirmed(st, 'exact:'+key, 'Bitte die genaue Marktauswahl beim Buchmacher prüfen.')
                        current = store.clock()
                        fresh = snapshot_loader(now=current)
                        current_day = store.history(scope).get(today)
                        current_bets = list(current_day['bets'].values()) if current_day else []
                        current_choices = daily3_choices(fresh.forecasts, now=current,
                            occupied_events=[b['event_id'] for b in current_bets if b['status'] != 'cancelled'],
                            occupied_guards=[b['snapshot']['event_guard'] for b in current_bets if b['status'] != 'cancelled'],
                            used_slots=day_balance(current_day).used_slots if current_day else 0)
                        matching = [c for c in current_choices[:1] if c.signal.key == signal_key]
                        current_fingerprint = (hashlib.sha256(json.dumps(matching[0].snapshot(), sort_keys=True).encode()).hexdigest()
                                               if len(matching) == 1 else None)
                        if current_fingerprint != fingerprint:
                            raise Daily3Error('Die Analyse hat sich seit der Anzeige verändert. Bitte den neuen Stand prüfen und erneut bestätigen.')
                        _require_reservation_price(matching[0], st.session_state['odds:'+key])
                        return dict(bet_id=_token(st, 'bet:'+key+fingerprint), snapshot=snap,
                                    stake_cents=parse_chf(st.session_state['stake:'+key], positive=True),
                                    odds=decimal_odds(st.session_state['odds:'+key]))
                    st.form_submit_button('Einsatz vormerken', **_callback(st, store, scope, 'reserve:'+key+fingerprint,
                        'reserve', today, reserve_args))
    publication_status = getattr(snapshot, 'status', None)
    if publication_status is not None:
        from daily3_selection import POLICY_VERSION
        from tip_publication import compact_signal_row, record_selected_tips
        publication_rows = [compact_signal_row(choice.signal,
            featured_role='daily3_ready' if can_reserve and index == 0 else 'daily3_plan')
            for index, choice in enumerate(choices)]
        record_selected_tips('daily3_plan', publication_rows, as_of=now,
            source_run_id=publication_status.generated_at.isoformat(), policy_version=POLICY_VERSION)
    visible_days = sorted({d['date'] for d in prior_pending} | ({today} if day else set()), reverse=True)
    for day_id in visible_days:
        bets = list(history[day_id]['bets'].values())
        if bets:
            st.subheader(f'Deine erfassten Wetten · {day_id}')
        for bet in bets:
            _saved_bet(st, store, scope, day_id, bet)
    older = [history[d] for d in sorted(history, reverse=True) if d not in visible_days]
    if older:
        st.subheader('Bisherige Tage – einschließlich Verluste')
        for old in older:
            result = day_balance(old)
            st.write(f'{old["date"]} · {result.placed_count} Wetten · Netto {format_chf(result.realised_cents)}')
        selected_day = st.selectbox('Frühere Belege anzeigen', ['Keine', *(d['date'] for d in older)])
        if selected_day != 'Keine':
            for bet in history[selected_day]['bets'].values():
                _saved_bet(st, store, scope, selected_day, bet)
    if storage_ready:
        _external_bet(st, store, scope, history, today, now)
    st.caption('Manuelle Erfassung · Keine Buchmacheranbindung · Verlustrisiko bleibt')
