"""Optional identity images for rendered cards; never part of a model or bet."""

from dataclasses import replace


def with_identity_images(card, signal, *, enabled=False):
    """Decorate a disposable presentation copy, without touching saved evidence."""
    if not enabled:
        return card
    from sports_identity_media import participant_image, participant_display_name

    sport = str(card.sport or '').casefold().replace('ß', 'ss').replace('-', '_').replace(' ', '_')
    kind = {'fussball': 'football', 'football': 'football', 'tennis': 'tennis',
            'basketball': 'basketball', 'eishockey': 'ice_hockey', 'ice_hockey': 'ice_hockey',
            'cricket': 'cricket', 'e_sport': 'esports', 'esport': 'esports', 'esports': 'esports'}.get(sport)
    if kind is None:
        return card
    source = card.fixture_source
    # The current automatic football reader retains native API-Football team
    # IDs, but older stored rows lack its optional display-source marker.
    # Infer only this existing validated producer, never a foreign namespace.
    if kind == 'football' and source is None:
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
    ids = (card.home_team_id, card.away_team_id) if kind == 'football' else (
        card.competitor_a_id, card.competitor_b_id)
    images = [participant_image(
        kind, name, team_id=team_id, fixture_source=source,
        context_evidence=getattr(signal, 'context_evidence', None), side=side,
        competition=getattr(signal, 'competition', None),
    ) if name else None for name, team_id, side in zip(names, ids, ('a', 'b'))]
    fields = {}
    if kind == 'ice_hockey':
        display_names = [participant_display_name(
            kind, name, team_id=team_id, fixture_source=source,
            competition=getattr(signal, 'competition', None),
        ) if name else name for name, team_id in zip(names, ids)]
        for side, original_name, display_name in zip(('home', 'away'), names, display_names):
            if display_name != original_name:
                fields['display_' + side + '_name'] = display_name
        if card.selection in names:
            selected_name = display_names[names.index(card.selection)]
            if selected_name != card.selection:
                fields['display_selection'] = selected_name
    for side, image in zip(('home', 'away'), images):
        if image is not None:
            fields[side + '_image'] = image.image_url
            fields[side + '_image_source'] = image.source_url
            fields[side + '_image_credit'] = image.credit
            fields[side + '_image_crop'] = getattr(image, 'crop', None)
    return replace(card, **fields) if fields else card


def rendered_identity_card(card, signal):
    """Image links decorate only actual UI cards, never saved model evidence."""
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    return with_identity_images(
        card, signal, enabled=get_script_run_ctx(suppress_warning=True) is not None,
    )


_IMAGE_FALLBACK_BRIDGE = """<!doctype html><html><body><script>
// Presentation only: no fetch, storage, account access or model callbacks.
(() => { try {
const host = window.parent;
const doc = host.document;
const previous = host.__bbIdentityImages;
if (previous && previous.version === 1) { previous.scan(); return; }
if (previous) previous.cleanup();
function paint(image) {
  if (!image.matches?.('.se-shield-image img')) return;
  const shield = image.closest('.se-shield-image');
  const loaded = image.complete && image.naturalWidth > 0;
  shield.classList.toggle('is-loaded', loaded);
  shield.classList.toggle('is-failed', image.complete && !loaded);
}
function scan() { doc.querySelectorAll('.se-shield-image img').forEach(paint); }
function onImage(event) { paint(event.target); }
doc.addEventListener('load', onImage, true);
doc.addEventListener('error', onImage, true);
let queued = false;
const observer = new host.MutationObserver(changes => {
  changes.filter(change => change.type === 'attributes').forEach(change => paint(change.target));
  if (!queued) {
    queued = true;
    host.requestAnimationFrame(() => { queued = false; scan(); });
  }
});
observer.observe(doc.querySelector('.stApp') || doc.body,
  {childList:true, subtree:true, attributes:true, attributeFilter:['src']});
host.__bbIdentityImages = {version:1, scan, cleanup() {
  observer.disconnect();
  doc.removeEventListener('load', onImage, true);
  doc.removeEventListener('error', onImage, true);
}};
scan();
} catch (_) { /* Isolated/restricted embeds retain their native initials. */ } })();
</script></body></html>"""


def install_image_fallback():
    """One invisible UI bridge replaces failed/lazy images with native initials."""
    from streamlit.runtime.scriptrunner import get_script_run_ctx
    if get_script_run_ctx(suppress_warning=True) is None:
        return
    from streamlit.components.v1 import html
    html(_IMAGE_FALLBACK_BRIDGE, height=0, scrolling=False)
