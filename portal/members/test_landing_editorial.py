"""Rendered landing-page contracts; no provider data or sports-model execution."""

import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from django.contrib.staticfiles import finders
from django.db import connection
from django.test import TestCase, override_settings

from .models import User


class Element:
    """Small HTML tree so contracts inspect the delivered DOM, not templates."""

    def __init__(self, tag, attrs=(), parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.parent = parent
        self.children = []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Element):
                yield from child.walk()

    def text(self):
        return " ".join(
            child.text() if isinstance(child, Element) else child
            for child in self.children
        ).strip()


class Document(HTMLParser):
    VOID_TAGS = {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    }

    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.current = self.root
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        element = Element(tag, attrs, self.current)
        self.current.children.append(element)
        if tag not in self.VOID_TAGS:
            self.current = element

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node is not self.root:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)

    def by_id(self, identity):
        return next(
            (node for node in self.root.walk() if node.attrs.get("id") == identity),
            None,
        )


class LandingEditorialTests(TestCase):
    def landing(self, lang="de"):
        response = self.client.get(f"/{lang}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Language"], lang)
        return Document(response.content.decode())

    def region(self, document, identity):
        node = document.by_id(identity)
        self.assertIsNotNone(node, f"Visitors need the {identity!r} section.")
        return node

    def assert_editorial_story(self, lang):
        document = self.landing(lang)
        sections = [node for node in document.root.walk() if node.tag == "section"]
        story = ("hero", "inside", "monthly-results", "plans", "closing-cta")
        positions = []
        for identity in story:
            section = self.region(document, identity)
            self.assertEqual(section.tag, "section")
            positions.append(sections.index(section))
            heading_tag = "h1" if identity == "hero" else "h2"
            self.assertTrue(
                any(node.tag == heading_tag and node.text() for node in section.walk()),
                f"The {identity} section needs a visible {heading_tag}.",
            )
        self.assertEqual(positions, sorted(positions), "The editorial story is out of order.")
        self.assertEqual(len([node for node in document.root.walk() if node.tag == "h1"]), 1)
        html = next(node for node in document.root.walk() if node.tag == "html")
        self.assertEqual(html.attrs.get("lang"), lang)
        return document

    # Break caught: deleting/reordering a public story section or losing its heading.
    def test_german_story_moves_from_hero_through_results_to_closing_cta(self):
        self.assert_editorial_story("de")

    def test_english_story_moves_from_hero_through_results_to_closing_cta(self):
        self.assert_editorial_story("en")

    # Break caught: a removed step leaves the visitor without the three-step explanation.
    def test_inside_explains_three_steps_in_both_languages(self):
        for lang in ("de", "en"):
            with self.subTest(lang=lang):
                inside = self.region(self.landing(lang), "inside")
                steps = [node for node in inside.walk() if node.tag == "article"]
                self.assertEqual(len(steps), 3)
                for step in steps:
                    self.assertTrue(any(node.tag == "h3" and node.text() for node in step.walk()))
                    self.assertTrue(any(node.tag == "p" and node.text() for node in step.walk()))

    def hero_preview(self, document):
        hero = self.region(document, "hero")
        figures = [node for node in hero.walk() if node.tag == "figure"]
        self.assertEqual(len(figures), 1, "The hero needs one honest product-preview figure.")
        images = [node for node in figures[0].walk() if node.tag == "img"]
        self.assertEqual(len(images), 1, "The preview must deliver a real image, not a fake live widget.")
        return figures[0], images[0]

    # Break caught: replacing the image with fake interactive product controls or a missing asset.
    def test_hero_preview_is_a_real_accessible_noninteractive_static_image(self):
        for lang, disclosure in (("de", "illustrativ"), ("en", "illustrative")):
            with self.subTest(lang=lang):
                figure, image = self.hero_preview(self.landing(lang))
                self.assertTrue(image.attrs.get("alt", "").strip())
                source = urlsplit(image.attrs.get("src", ""))
                self.assertFalse(source.scheme or source.netloc)
                self.assertTrue(source.path.startswith("/portal-static/portal/editorial/"))
                asset = finders.find(source.path.removeprefix("/portal-static/"))
                self.assertIsNotNone(asset, "The delivered image URL must resolve to a real static asset.")
                self.assertTrue(Path(asset).is_file())
                captions = [node for node in figure.walk() if node.tag == "figcaption"]
                self.assertEqual(len(captions), 1)
                self.assertIn(disclosure, captions[0].text().casefold())
                for node in figure.walk():
                    self.assertNotIn(node.tag, {"a", "button", "input", "select", "textarea", "form", "iframe"})
                    self.assertNotEqual(node.attrs.get("role"), "button")
                    self.assertNotIn("tabindex", node.attrs)
                    self.assertFalse(any(name.startswith("on") for name in node.attrs))

    # Break caught: omitting intrinsic geometry or serving only a fixed large image on mobile.
    def test_hero_preview_reserves_square_geometry_and_has_responsive_image_candidates(self):
        figure, image = self.hero_preview(self.landing())
        width, height = image.attrs.get("width", ""), image.attrs.get("height", "")
        self.assertTrue(width.isdecimal() and height.isdecimal(), "Intrinsic dimensions prevent image layout shift.")
        self.assertGreaterEqual(int(width), 640)
        self.assertEqual(int(width), int(height))
        responsive = [node for node in figure.walk() if node.tag in {"img", "source"} and node.attrs.get("srcset")]
        self.assertTrue(responsive, "Mobile visitors need width-based image candidates.")
        for node in responsive:
            candidates = [candidate.strip() for candidate in node.attrs["srcset"].split(",")]
            self.assertGreaterEqual(len(candidates), 2)
            widths = []
            for candidate in candidates:
                self.assertRegex(candidate, r"^/portal-static/portal/editorial/[^\s]+\s+\d+w$")
                widths.append(int(candidate.rsplit(" ", 1)[1][:-1]))
            self.assertGreater(len(set(widths)), 1)
            self.assertIn("max-width", node.attrs.get("sizes", ""))
            self.assertIn("vw", node.attrs.get("sizes", ""))

    def test_each_language_uses_its_localized_campaign_assets(self):
        for lang in ("de", "en"):
            suffix = "-en" if lang == "en" else ""
            document = self.landing(lang)
            for region, stem in (("hero", "hero"), ("closing-cta", "stadium")):
                with self.subTest(lang=lang, region=region):
                    images = [node for node in self.region(document, region).walk()
                              if node.tag == "img" and node.attrs.get("src", "").endswith(".webp")]
                    self.assertEqual(len(images), 1)
                    self.assertTrue(images[0].attrs["src"].endswith(f"/{stem}{suffix}.webp"))
                    for candidate in images[0].attrs["srcset"].split(","):
                        path = candidate.strip().split()[0].removeprefix("/portal-static/")
                        self.assertIsNotNone(finders.find(path), path)

    # Break caught: fabricated win-rate/return metrics replacing an unpublished-results state.
    def test_monthly_results_discloses_unpublished_state_without_invented_performance(self):
        for lang, unavailable in (("de", "noch keine veröffentlichte"), ("en", "no published")):
            with self.subTest(lang=lang):
                results = self.region(self.landing(lang), "monthly-results")
                visible = results.text().casefold()
                self.assertIn("september", visible)
                self.assertIn("2026", visible)
                self.assertIn(unavailable, visible)
                self.assertNotRegex(visible, r"\d+(?:[.,]\d+)?\s*%")
                self.assertNotRegex(visible, r"[+−-]\s*(?:chf\s*)?\d")
                self.assertNotRegex(visible, r"\b\d+\s+(?:tipps|picks|wetten|bets|wins|treffer)\b")

    # Break caught: a tier hides included features or shows another tier's actual CHF price.
    def test_plan_cards_show_full_included_features_with_the_correct_tier_prices(self):
        features = {
            "de": (
                "Automatischer Wettfinder", "Tipps speichern & verfolgen",
                "Eigene Spiel- und Marktsuche", "RisikoBet: Außenseiter-Szenarien",
                "Live-Bereich", "Daily3-Tagesplan", "15K-Challenge",
            ),
            "en": (
                "Automatic match finder", "Save & track your picks",
                "Custom game & market search", "RisikoBet: underdog scenarios",
                "Live workspace", "Daily3 daily plan", "15K Challenge",
            ),
        }
        for lang in ("de", "en"):
            plans = self.region(self.landing(lang), "plans")
            cards = [node for node in plans.walk() if node.tag == "article"]
            self.assertEqual(len(cards), 3)
            for name, price, feature_count in (("Starter", "9.90", 2), ("Plus", "19.90", 4), ("Pro", "29.90", 7)):
                with self.subTest(lang=lang, plan=name):
                    matching = [card for card in cards if any(node.tag == "h3" and node.text() == name for node in card.walk())]
                    self.assertEqual(len(matching), 1)
                    card = matching[0]
                    self.assertIn("CHF", card.text())
                    self.assertIn(price, card.text())
                    included = [node.text() for node in card.walk() if node.tag == "li"]
                    for feature in features[lang][:feature_count]:
                        self.assertTrue(any(feature in item for item in included), f"{name} hides its included feature: {feature}")

    # Break caught: the public pricing comparison implies that paying more buys better models.
    def test_each_plan_discloses_the_same_analysis_quality(self):
        for lang, disclosure in (("de", "gleiche analyse-qualität in allen abos"), ("en", "same analysis quality in every plan")):
            with self.subTest(lang=lang):
                plans = self.region(self.landing(lang), "plans")
                cards = [node for node in plans.walk() if node.tag == "article"]
                self.assertEqual(len(cards), 3)
                for card in cards:
                    self.assertIn(disclosure, card.text().casefold())

    # Break caught: a plan CTA loses its plan key or leads away from the existing registration flow.
    def test_anonymous_plan_links_keep_the_selected_plan_and_open_registration(self):
        for lang in ("de", "en"):
            with self.subTest(lang=lang):
                plans = self.region(self.landing(lang), "plans")
                links = [node for node in plans.walk() if node.tag == "a"]
                selected = []
                for link in links:
                    address = urlsplit(link.attrs.get("href", ""))
                    if address.path != f"/{lang}/register/":
                        continue
                    plan = parse_qs(address.query).get("plan", [])
                    self.assertEqual(len(plan), 1)
                    selected.append(plan[0])
                    response = self.client.get(link.attrs["href"])
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(self.client.session.get("chosen_plan"), plan[0])
                    self.assertEqual(response.context["chosen_plan"]["name"], {"starter": "Starter", "plus": "Plus", "pro": "Pro"}[plan[0]])
                self.assertCountEqual(selected, ("starter", "plus", "pro"))
                self.assertEqual(User.objects.count(), 0, "Looking at plans must not create customers.")

    # Break caught: a signed-in visitor is sent back into registration or directly to unverified access.
    def test_authenticated_plan_links_route_to_the_existing_account(self):
        user = User.objects.create_user("landing@example.test", "landing-unique-passphrase-42!")
        self.client.force_login(user)
        for lang in ("de", "en"):
            with self.subTest(lang=lang):
                plans = self.region(self.landing(lang), "plans")
                cards = [node for node in plans.walk() if node.tag == "article"]
                self.assertEqual(len(cards), 3)
                for card in cards:
                    links = [node for node in card.walk() if node.tag == "a"]
                    self.assertEqual(len(links), 1)
                    self.assertEqual(links[0].attrs.get("href"), f"/{lang}/account/")
                    self.assertEqual(self.client.get(links[0].attrs["href"]).status_code, 200)

    # Break caught: a renamed section leaves navigation or a closing CTA pointing at nothing.
    def test_local_anchor_navigation_targets_rendered_sections(self):
        for lang in ("de", "en"):
            with self.subTest(lang=lang):
                document = self.landing(lang)
                for link in (node for node in document.root.walk() if node.tag == "a"):
                    address = urlsplit(link.attrs.get("href", ""))
                    if not address.scheme and address.path in ("", f"/{lang}/") and address.fragment:
                        self.assertIsNotNone(document.by_id(address.fragment), f"Broken navigation target: {link.attrs['href']}")
                closing = self.region(document, "closing-cta")
                self.assertTrue(any(node.tag == "a" and node.attrs.get("href") in {"#plans", f"/{lang}/#plans"} for node in closing.walk()))

    # Break caught: inherited account/navigation links outlive a removed landing section.
    def test_shared_auth_navigation_targets_existing_landing_sections(self):
        for lang in ("de", "en"):
            home = self.landing(lang)
            for page in ("login", "register", "password/reset"):
                with self.subTest(lang=lang, page=page):
                    response = self.client.get(f"/{lang}/{page}/")
                    self.assertEqual(response.status_code, 200)
                    document = Document(response.content.decode())
                    for link in (node for node in document.root.walk() if node.tag == "a"):
                        address = urlsplit(link.attrs.get("href", ""))
                        if address.path == f"/{lang}/" and address.fragment:
                            self.assertIsNotNone(home.by_id(address.fragment), link.attrs["href"])

    # Break caught: opening the public landing makes outbound provider calls or writes account data.
    def test_public_render_is_read_only_and_does_not_call_providers(self):
        def read_only(execute, sql, params, many, context):
            statement = sql.lstrip().split(None, 1)[0].upper()
            self.assertNotIn(statement, {"INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "ALTER", "DROP"})
            return execute(sql, params, many, context)

        with patch("socket.socket.connect", side_effect=AssertionError("Landing rendering must not make provider requests.")):
            with connection.execute_wrapper(read_only):
                for lang in ("de", "en"):
                    document = self.landing(lang)
                    text = document.root.text().casefold()
                    for private_field in ("sourcepool", "source_pool", "payload_json", "scan_run_id", "provider_budget"):
                        self.assertNotIn(private_field, text)

    # Break caught: the redesign hides the sales gate and advertises an already-launched product.
    @override_settings(REGISTRATION_OPEN=False, LEGAL_READY=False)
    def test_closed_sales_remains_visibly_a_preview(self):
        for lang, status in (("de", "verkauf noch nicht gestartet"), ("en", "sales have not opened")):
            with self.subTest(lang=lang):
                document = self.landing(lang)
                self.assertIn(status, document.root.text().casefold())
                for link in (node for node in document.root.walk() if node.tag == "a"):
                    address = urlsplit(link.attrs.get("href", ""))
                    self.assertNotEqual(address.hostname, "apps.apple.com")
                    self.assertFalse(address.hostname == "play.google.com" and address.path.startswith("/store"))
