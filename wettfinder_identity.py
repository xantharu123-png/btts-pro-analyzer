"""Optional identity images for rendered cards; never part of a model or bet."""

from dataclasses import replace


def with_identity_images(card, signal, *, enabled=False):
    """Decorate a disposable presentation copy, without touching saved evidence."""
    if not enabled:
        return card
    from sports_identity_media import participant_image

    sport = str(card.sport or '').casefold().replace('ß', 'ss')
    if sport not in {'fussball', 'football', 'tennis'}:
        return card
    source = card.fixture_source
    # The current automatic football reader retains native API-Football team
    # IDs, but older stored rows lack its optional display-source marker.
    # Infer only this existing validated producer, never a foreign namespace.
    if sport in {'fussball', 'football'} and source is None:
        evidence = getattr(signal, 'analysis_evidence', None)
        binding = evidence.get('identity', {}) if isinstance(evidence, dict) else {}
        if (isinstance(evidence, dict) and isinstance(binding, dict)
                and signal.source == 'automated_wettfinder_forecast'
                and evidence.get('schema') == 'football-card-analysis-v1'
                and binding.get('fixture_id') == card.fixture_id
                and binding.get('home_id') == card.home_team_id
                and binding.get('away_id') == card.away_team_id
                and binding.get('home_team') == card.home_team
                and binding.get('away_team') == card.away_team):
            source = 'api_football'
    names = (card.home_team or card.competitor_a, card.away_team or card.competitor_b)
    ids = (card.home_team_id, card.away_team_id)
    kind = 'tennis' if sport == 'tennis' else 'football'
    images = [participant_image(
        kind, name, team_id=team_id, fixture_source=source,
        context_evidence=getattr(signal, 'context_evidence', None), side=side,
    ) if name else None for name, team_id, side in zip(names, ids, ('a', 'b'))]
    if not any(images):
        return card
    fields = {}
    for side, image in zip(('home', 'away'), images):
        if image is not None:
            fields[side + '_image'] = image.data_uri
            fields[side + '_image_source'] = image.source_url
            fields[side + '_image_credit'] = image.credit
            fields[side + '_image_crop'] = getattr(image, 'crop', None)
    return replace(card, **fields)


def rendered_identity_card(card, signal):
    """Images load only in an actual Streamlit UI, not scans or pure renderers."""
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    return with_identity_images(
        card, signal, enabled=get_script_run_ctx(suppress_warning=True) is not None,
    )
