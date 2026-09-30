"""Safe presentation-only portraits/crests inside the existing editorial shield."""
from base64 import b64encode
from copy import deepcopy
from dataclasses import fields, replace
from html.parser import HTMLParser
from io import BytesIO
import re

from PIL import Image
import pytest

import wettfinder_surface as surface
from editorial_theme import editorial_css
from test_wettfinder_surface import NOW, _quote, _signal


IMAGE_FIELDS = {
    "home_image", "away_image", "home_image_credit", "away_image_credit",
    "home_image_source", "away_image_source", "home_image_crop", "away_image_crop",
}
COMMONS_SOURCE = "https://commons.wikimedia.org/wiki/File:Verified_test_image.png"


def raster_uri(format="PNG", *, size=(16, 20)):
    output = BytesIO()
    Image.new("RGB", size, (90, 120, 150)).save(output, format=format)
    mime = {"PNG": "png", "JPEG": "jpeg", "WEBP": "webp"}[format]
    return f"data:image/{mime};base64,{b64encode(output.getvalue()).decode('ascii')}"


def card_for(sport="Fussball"):
    return surface.build_wettfinder_card(_signal(sport=sport), now=NOW)


class Tags(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.tags = []
        self.feed(markup)

    def handle_starttag(self, tag, attributes):
        self.tags.append((tag, dict(attributes)))


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP"])
@pytest.mark.parametrize("sport, kind", [("Fussball", "football"), ("Fußball", "football"), ("Tennis", "tennis")])
def test_verified_raster_is_inside_same_shield_with_sport_specific_fit(format, sport, kind):
    uri = raster_uri(format)
    card = replace(card_for(sport), home_image=uri, away_image=uri)
    html = surface.render_match_header_html(card)
    tags = Tags(html).tags
    images = [attributes for tag, attributes in tags if tag == "img"]
    assert len(images) == 2
    assert all(image == {"src": uri, "alt": "", "decoding": "async", "loading": "lazy"} for image in images)
    assert html.count(f'class="se-shield se-shield-image se-shield-{kind}" aria-hidden="true"') == 2
    assert html.count('<strong>') == 2
    assert "©" not in html  # No invented license/source when metadata is absent.


@pytest.mark.parametrize("bad_uri", [
    None, "", False, [], {},
    "https://upload.wikimedia.org/example.png",
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
    html = surface.render_match_header_html(replace(card_for(), home_image=raster_uri()))
    assert html.count('<img ') == 1
    assert '<span class="se-shield" aria-hidden="true">B</span>' in html


@pytest.mark.parametrize("crop, expected", [
    ((50, 20, 2), 'transform:scale(2);transform-origin:50% 20%'),
    ([35.5, 17.25, 1.75], 'transform:scale(1.75);transform-origin:35.5% 17.25%'),
    ((0, -0.0, 1), 'transform:scale(1);transform-origin:0% 0%'),
    ((100, 100, 3), 'transform:scale(3);transform-origin:100% 100%'),
])
def test_valid_focal_point_zoom_stays_in_original_clipped_shield_without_changing_bytes(crop, expected):
    uri = raster_uri()
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
    uri = raster_uri()
    html = surface.render_match_header_html(replace(card_for("Tennis"), home_image=uri, home_image_crop=crop))
    images = [attributes for tag, attributes in Tags(html).tags if tag == 'img']
    assert len(images) == 1 and images[0]['src'] == uri
    assert 'style' not in images[0]
    assert 'transform:' not in html and 'javascript:' not in html
    assert not any(name.startswith('on') for _tag, attributes in Tags(html).tags for name in attributes)


def test_crop_without_valid_raster_keeps_initials_and_emits_no_style():
    html = surface.render_match_header_html(replace(card_for("Tennis"), home_image_crop=(50, 20, 2)))
    assert '<img ' not in html and 'style=' not in html
    assert '<span class="se-shield" aria-hidden="true">A</span>' in html


def test_mime_mismatch_corrupted_crc_and_truncated_jpeg_are_rejected():
    png = raster_uri()
    jpeg = raster_uri("JPEG")
    from base64 import b64decode
    corrupt = bytearray(b64decode(png.split(",", 1)[1]))
    corrupt[-1] ^= 1  # Break the IEND checksum without changing a valid PNG signature.
    truncated = b64decode(jpeg.split(",", 1)[1])[:-20]
    for invalid in (
        png.replace("image/png", "image/jpeg"),
        jpeg.replace("image/jpeg", "image/webp"),
        "data:image/png;base64," + b64encode(corrupt).decode("ascii"),
        "data:image/jpeg;base64," + b64encode(truncated).decode("ascii"),
    ):
        html = surface.render_match_header_html(replace(card_for(), home_image=invalid))
        assert '<img ' not in html


def test_oversized_raster_or_uri_are_rejected_without_browser_payload():
    for invalid in (
        raster_uri(size=(2049, 2)),
        "data:image/png;base64," + "A" * surface._IDENTITY_IMAGE_MAX_URI_LENGTH,
    ):
        assert '<img ' not in surface.render_match_header_html(replace(card_for(), home_image=invalid))


def test_animated_raster_is_not_a_static_identity_portrait():
    output = BytesIO()
    Image.new("RGB", (16, 20), "red").save(
        output, format="PNG", save_all=True,
        append_images=[Image.new("RGB", (16, 20), "blue")], duration=100,
    )
    uri = "data:image/png;base64," + b64encode(output.getvalue()).decode("ascii")
    assert '<img ' not in surface.render_match_header_html(replace(card_for(), home_image=uri))


def test_commons_credit_link_is_outside_clipped_shield_and_escaped():
    card = replace(card_for(), home_team='<Alpha & "Beta">', home_image=raster_uri(),
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
    html = surface.render_match_header_html(replace(card_for(), home_image=raster_uri(),
        home_image_source=bad_source, home_image_credit="Author"))
    assert html.count('<img ') == 1
    assert '<a ' not in html and '©' not in html


def test_encoded_commons_file_name_is_valid_and_unknown_credit_is_not_invented():
    source = "https://commons.wikimedia.org/wiki/File:Jos%C3%A9_Test%20portrait.jpg"
    html = surface.render_match_header_html(replace(card_for("Tennis"), home_image=raster_uri(),
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
    decorated = replace(undecorated, home_image=raster_uri(), away_image=raster_uri("JPEG"),
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
        event_label="A < B", home_image=raster_uri())
    assert surface.render_match_header_html(missing) == '<p class="se-event">A &lt; B</p>'
    other = replace(card_for("Basketball"), home_image=raster_uri(), home_image_source=COMMONS_SOURCE)
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
    assert '.se-shield-image, .se-team:last-child .se-shield-image {background:var(--bb-surface);}' in css
    assert re.search(r'\.se-image-credit \{[^}]*max-width:78px;[^}]*white-space:nowrap;', css)
    assert '.se-image-credit:focus-visible' in css
