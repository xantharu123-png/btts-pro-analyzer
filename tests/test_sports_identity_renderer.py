"""Safe presentation-only portraits/crests inside the existing editorial shield."""
from copy import deepcopy
from dataclasses import fields, replace
from html.parser import HTMLParser
import re

import pytest

import wettfinder_surface as surface
from editorial_theme import editorial_css
from test_wettfinder_surface import NOW, _quote, _signal


IMAGE_FIELDS = {
    "home_image", "away_image", "home_image_credit", "away_image_credit",
    "home_image_source", "away_image_source", "home_image_crop", "away_image_crop",
}
COMMONS_SOURCE = "https://commons.wikimedia.org/wiki/File:Verified_test_image.png"
FOOTBALL_IMAGE = "https://media.api-sports.io/football/teams/212.png"
TENNIS_IMAGE = "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Verified_test_image.png/330px-Verified_test_image.png"
BASKETBALL_IMAGE = "https://a.espncdn.com/i/teamlogos/nba/500/2.png"
HOCKEY_IMAGE = "https://assets.nhle.com/logos/nhl/svg/TOR_light.svg"
CRICKET_IMAGE = "https://static.cricbuzz.com/a/img/v1/152x152/i1/c776162/india.jpg"
ESPORT_IMAGE = "https://thumb.wikimedia.org/wikipedia/commons/thumb/f/f5/Team_Spirit_new_em.svg/330px-Team_Spirit_new_em.svg.png"


def card_for(sport="Fussball"):
    return surface.build_wettfinder_card(_signal(sport=sport), now=NOW)


class Tags(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.tags = []
        self.feed(markup)

    def handle_starttag(self, tag, attributes):
        self.tags.append((tag, dict(attributes)))


@pytest.mark.parametrize("sport, kind, uri", [
    ("Fussball", "football", FOOTBALL_IMAGE),
    ("Fußball", "football", FOOTBALL_IMAGE),
    ("Tennis", "tennis", TENNIS_IMAGE),
    ("Basketball", "basketball", BASKETBALL_IMAGE),
    ("Eishockey", "ice_hockey", HOCKEY_IMAGE),
    ("Cricket", "cricket", CRICKET_IMAGE),
    ("E-Sport", "esports", ESPORT_IMAGE),
])
def test_allowlisted_remote_image_is_inside_same_shield_with_sport_specific_fit(uri, sport, kind):
    card = replace(card_for(sport), home_image=uri, away_image=uri)
    html = surface.render_match_header_html(card)
    tags = Tags(html).tags
    images = [attributes for tag, attributes in tags if tag == "img"]
    assert len(images) == 2
    assert all(image == {"src": uri, "alt": "", "decoding": "async", "loading": "lazy", "referrerpolicy": "no-referrer"} for image in images)
    assert html.count(f'class="se-shield se-shield-image se-shield-{kind}" aria-hidden="true"') == 2
    assert html.count('<span class="se-image-initials">') == 2
    assert '<span class="se-image-initials">A</span>' in html
    assert '<span class="se-image-initials">B</span>' in html
    assert 'is-loaded' not in html  # Only successful browser loading can grant this state.
    assert html.count('<strong>') == 2
    assert "©" not in html  # No invented license/source when metadata is absent.


@pytest.mark.parametrize("sport, uri", [
    ("Fussball", TENNIS_IMAGE), ("Tennis", FOOTBALL_IMAGE),
    ("Tennis", ESPORT_IMAGE), ("Tennis", "https://thumb.wikimedia.org/wikipedia/commons/thumb/3/39/MOUZlogo2021.png/330px-MOUZlogo2021.png"),
    ("Basketball", HOCKEY_IMAGE), ("Eishockey", BASKETBALL_IMAGE),
    ("Cricket", FOOTBALL_IMAGE), ("E-Sport", TENNIS_IMAGE),
])
def test_allowlisted_source_for_other_sport_keeps_initials(sport, uri):
    html = surface.render_match_header_html(replace(card_for(sport), home_image=uri,
        home_image_source=COMMONS_SOURCE))
    assert '<span class="se-shield" aria-hidden="true">A</span>' in html
    assert '<img ' not in html and '<a ' not in html


@pytest.mark.parametrize("bad_uri", [
    None, "", False, [], {},
    "https://upload.wikimedia.org/example.png",
    "https://example.com/image.png",
    "http://media.api-sports.io/football/teams/212.png",
    "https://media.api-sports.io.evil.example/football/teams/212.png",
    "https://media.api-sports.io@evil.example/football/teams/212.png",
    "https://evil.example@media.api-sports.io/football/teams/212.png",
    "https://media.api-sports.io:443/football/teams/212.png",
    "https://media.api-sports.io/football/teams/0.png",
    "https://media.api-sports.io/football/teams/212.svg",
    "https://media.api-sports.io/football/teams/212.png?secret=x",
    "https://media.api-sports.io/football/teams/212.png#fragment",
    "https://media.api-sports.io/football/teams/212.png%0A",
    "https://upload.wikimedia.org/wikipedia/commons/a/ab/Verified_test_image.png",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Verified_test_image.png/401px-Verified_test_image.png",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Verified_test_image.png/330px-Other_file.png",
    "https://thumb.wikimedia.org/wikipedia/commons/thumb/a/ab/Verified_test_image.svg/330px-Verified_test_image.svg",
    "javascript:alert(1)",
    'x" onerror="alert(1)',
    "data:image/svg+xml;base64,PHN2ZyBvbmxvYWQ9YWxlcnQoMSk+PC9zdmc+",
    "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
    "data:image/png;base64,%%%%",
    "data:image/png;base64,AA",
    "data:image/png;base64,",
    "data:image/png;base64,AA==\n",
    "data:image/png;base64,PHN2Zz48L3N2Zz4=",
    "data:image/png;base64,SGVsbG8=",
])
def test_unsafe_missing_or_malformed_image_falls_back_to_initials(bad_uri):
    card = replace(card_for(), home_image=bad_uri, home_image_source=COMMONS_SOURCE)
    html = surface.render_match_header_html(card)
    assert '<span class="se-shield" aria-hidden="true">A</span>' in html
    assert '<span class="se-shield" aria-hidden="true">B</span>' in html
    assert '<img' not in html and '<a ' not in html
    assert "onerror" not in html and "javascript:" not in html


def test_valid_image_does_not_displace_other_side_fallback():
    html = surface.render_match_header_html(replace(card_for(), home_image=FOOTBALL_IMAGE))
    assert html.count('<img ') == 1
    assert '<span class="se-shield" aria-hidden="true">B</span>' in html


@pytest.mark.parametrize("crop, expected", [
    ((50, 20, 2), 'transform:scale(2);transform-origin:50% 20%'),
    ([35.5, 17.25, 1.75], 'transform:scale(1.75);transform-origin:35.5% 17.25%'),
    ((0, -0.0, 1), 'transform:scale(1);transform-origin:0% 0%'),
    ((100, 100, 3), 'transform:scale(3);transform-origin:100% 100%'),
])
def test_valid_focal_point_zoom_stays_in_original_clipped_shield_without_changing_url(crop, expected):
    uri = TENNIS_IMAGE
    card = replace(card_for("Tennis"), home_image=uri, away_image=uri,
        home_image_crop=crop, away_image_crop=(60, 30, 1.5))
    html = surface.render_match_header_html(card)
    images = [attributes for tag, attributes in Tags(html).tags if tag == 'img']
    assert images[0]['style'] == expected
    assert images[1]['style'] == 'transform:scale(1.5);transform-origin:60% 30%'
    assert all(image['src'] == uri for image in images)
    assert html.count('class="se-shield se-shield-image se-shield-tennis"') == 2
    assert card.home_image_crop == crop


@pytest.mark.parametrize("crop", [
    None, '', '50 20 2', 'transform:scale(2);background:url(javascript:alert(1))',
    '50% 20%" onerror="alert(1)', {"x": 50, "y": 20, "scale": 2},
    (), [], (50, 20), (50, 20, 2, 1),
    (True, 20, 2), (50, False, 2), (50, 20, True),
    ('50', 20, 2), (50, '20%;background:url(x)', 2), (50, 20, '2" onclick="evil'),
    (float('nan'), 20, 2), (50, float('inf'), 2), (50, 20, float('-inf')),
    (-.01, 20, 2), (100.01, 20, 2), (50, -.01, 2), (50, 100.01, 2),
    (50, 20, .999), (50, 20, 3.001), (2**2048, 20, 2),
])
def test_invalid_crop_never_exports_styles_or_handlers(crop):
    uri = TENNIS_IMAGE
    html = surface.render_match_header_html(replace(card_for("Tennis"), home_image=uri, home_image_crop=crop))
    images = [attributes for tag, attributes in Tags(html).tags if tag == 'img']
    assert len(images) == 1 and images[0]['src'] == uri
    assert 'style' not in images[0]
    assert 'transform:' not in html and 'javascript:' not in html
    assert not any(name.startswith('on') for _tag, attributes in Tags(html).tags for name in attributes)


def test_crop_without_allowlisted_image_keeps_initials_and_emits_no_style():
    html = surface.render_match_header_html(replace(card_for("Tennis"), home_image_crop=(50, 20, 2)))
    assert '<img ' not in html and 'style=' not in html
    assert '<span class="se-shield" aria-hidden="true">A</span>' in html


def test_oversized_remote_url_is_rejected_without_browser_payload():
    uri = FOOTBALL_IMAGE + "A" * 2048
    assert '<img ' not in surface.render_match_header_html(replace(card_for(), home_image=uri))


def test_commons_credit_link_is_outside_clipped_shield_and_escaped():
    card = replace(card_for("Tennis"), competitor_a='<Alpha & "Beta">', home_image=TENNIS_IMAGE,
        home_image_source=COMMONS_SOURCE, home_image_credit='<script>alert("credit")</script> & Author')
    html = surface.render_match_header_html(card)
    assert '</span><a class="se-image-credit"' in html
    assert f'href="{COMMONS_SOURCE}" target="_blank" rel="noopener noreferrer"' in html
    assert 'title="&lt;script&gt;alert(&quot;credit&quot;)&lt;/script&gt; &amp; Author"' in html
    assert 'aria-label="Bildnachweis: &lt;script&gt;alert(&quot;credit&quot;)&lt;/script&gt; &amp; Author"' in html
    assert '>© Foto</a>' in html
    assert re.findall(r'<a [^>]+>([^<]+)</a>', html) == ['© Foto']
    assert '<strong>&lt;Alpha &amp; &quot;Beta&quot;&gt;</strong>' in html
    assert all(tag not in {"script", "svg", "iframe"} for tag, _attributes in Tags(html).tags)
    assert not any(name.startswith("on") for _tag, attributes in Tags(html).tags for name in attributes)


def test_esport_logo_credit_is_preserved_as_logo_not_player_photo():
    source = "https://commons.wikimedia.org/wiki/File:Team_Spirit_new_em.svg"
    credit = "Team Spirit · CC BY-SA 4.0 · unverändert skaliert"
    card = replace(card_for("E-Sport"), home_image=ESPORT_IMAGE,
                   home_image_source=source, home_image_credit=credit)
    html = surface.render_match_header_html(card)
    assert f'href="{source}"' in html
    assert f'title="{credit}"' in html and '>© Logo</a>' in html
    assert '>© Foto</a>' not in html


def test_official_nhl_svg_is_only_external_img_never_inline_or_object():
    html = surface.render_match_header_html(replace(card_for("Eishockey"), home_image=HOCKEY_IMAGE))
    assert f'src="{HOCKEY_IMAGE}"' in html
    assert not any(tag in {"svg", "object", "embed", "script"} for tag, _attrs in Tags(html).tags)


@pytest.mark.parametrize("bad_source", [
    None, False, [], "", "javascript:alert(1)",
    "http://commons.wikimedia.org/wiki/File:Test.png",
    "https://example.com/wiki/File:Test.png",
    "https://commons.wikimedia.org.evil.example/wiki/File:Test.png",
    "https://commons.wikimedia.org@evil.example/wiki/File:Test.png",
    "https://evil.example@commons.wikimedia.org/wiki/File:Test.png",
    "https://commons.wikimedia.org:443/wiki/File:Test.png",
    "https://commons.wikimedia.org/wiki/Special:Redirect/file/Test.png",
    "https://commons.wikimedia.org/wiki/File:",
    "https://commons.wikimedia.org/wiki/File:Test.png?redirect=https://example.com",
    "https://commons.wikimedia.org/wiki/File:Test.png#fragment",
    'https://commons.wikimedia.org/wiki/File:Test.png" onclick="alert(1)',
    "https://commons.wikimedia.org/wiki/File:Test%0A.png",
    "https://commons.wikimedia.org/wiki/File:Test%00.png",
    "https://commons.wikimedia.org/wiki/File:Test%xx.png",
])
def test_non_commons_or_unsafe_credit_source_never_becomes_link(bad_source):
    html = surface.render_match_header_html(replace(card_for("Tennis"), home_image=TENNIS_IMAGE,
        home_image_source=bad_source, home_image_credit="Author"))
    assert html.count('<img ') == 1
    assert '<a ' not in html and '©' not in html


def test_encoded_commons_file_name_is_valid_and_unknown_credit_is_not_invented():
    source = "https://commons.wikimedia.org/wiki/File:Jos%C3%A9_Test%20portrait.jpg"
    html = surface.render_match_header_html(replace(card_for("Tennis"), home_image=TENNIS_IMAGE,
        home_image_source=source))
    assert f'href="{source}"' in html
    assert 'title="Wikimedia Commons" aria-label="Bildnachweis: Wikimedia Commons">© Foto</a>' in html


def test_image_decoration_preserves_all_model_price_and_event_fields(monkeypatch):
    signal = _signal()
    signal_before = deepcopy(vars(signal))
    quote = _quote(signal)
    quote_before = deepcopy(vars(quote))
    monkeypatch.setattr(surface, '_safe_identity_image_uri', lambda _value: pytest.fail('builder resolved image'))
    undecorated = surface.build_wettfinder_card(signal, quote, now=NOW)
    assert all(getattr(undecorated, name) is None for name in IMAGE_FIELDS)
    assert IMAGE_FIELDS.issubset({field.name for field in fields(surface.WettfinderCard)})
    monkeypatch.undo()
    decorated = replace(undecorated, home_image=FOOTBALL_IMAGE, away_image=FOOTBALL_IMAGE,
        home_image_credit="Author", home_image_source=COMMONS_SOURCE,
        home_image_crop=(50, 20, 2), away_image_crop=(60, 30, 1.5))
    surface.render_match_header_html(decorated)
    surface.render_editorial_card_html(decorated, grouped=True, include_match=True)
    assert {key: value for key, value in vars(decorated).items() if key not in IMAGE_FIELDS} == {
        key: value for key, value in vars(undecorated).items() if key not in IMAGE_FIELDS
    }
    assert vars(signal) == signal_before and vars(quote) == quote_before


def test_missing_event_names_and_other_sports_keep_existing_fallback():
    missing = replace(card_for("Tennis"), competitor_a=None, competitor_b=None,
        event_label="A < B", home_image=TENNIS_IMAGE)
    assert surface.render_match_header_html(missing) == '<p class="se-event">A &lt; B</p>'
    other = replace(card_for("Basketball"), home_image=FOOTBALL_IMAGE, home_image_source=COMMONS_SOURCE)
    assert '<img ' not in surface.render_match_header_html(other)


def test_shield_polygon_inner_border_and_320_390_dimensions_are_unchanged():
    css = editorial_css()
    polygon = 'clip-path:polygon(50% 0,100% 18%,95% 78%,50% 100%,5% 78%,0 18%)'
    assert css.count(polygon) == 2
    assert re.search(r'\.se-shield \{[^}]*width:78px;height:94px;[^}]*border:5px', css)
    assert '.se-shield:after {content:\'\';position:absolute;inset:4px;border:2px solid #ffffffa0;' in css
    assert '@media(max-width:760px)' in css
    assert '.se-shield {flex-basis:70px;width:60px;height:70px;font-size:1.1rem;}' in css
    assert '.se-shield-tennis img {object-fit:cover;object-position:center 22%;}' in css
    assert 'object-fit:contain;padding:13px 10px 17px;' in css
    assert '.se-shield-basketball img, .se-shield-ice_hockey img, .se-shield-esports img, .se-shield-cricket img' in css
    assert '.se-shield-image.is-loaded, .se-team:last-child .se-shield-image.is-loaded {background:var(--bb-surface);}' in css
    assert re.search(r'\.se-image-credit \{[^}]*max-width:78px;[^}]*white-space:nowrap;', css)
    assert '.se-image-credit:focus-visible' in css


def test_pending_or_failed_image_keeps_initials_and_hides_credit_until_success():
    html = surface.render_match_header_html(replace(card_for("Tennis"), home_image=TENNIS_IMAGE,
        home_image_source=COMMONS_SOURCE, home_image_credit="Author"))
    css = editorial_css()
    assert '<span class="se-image-initials">A</span>' in html
    assert 'is-loaded' not in html
    assert re.search(r'\.se-shield-image img \{[^}]*opacity:0;', css)
    assert '.se-shield-image.is-loaded img {opacity:1;}' in css
    assert '.se-shield-image.is-loaded .se-image-initials {visibility:hidden;}' in css
    assert '.se-identity:has(.se-shield-image:not(.is-loaded)) .se-image-credit {visibility:hidden;}' in css
    assert not any(name.startswith("on") for _tag, attributes in Tags(html).tags for name in attributes)
