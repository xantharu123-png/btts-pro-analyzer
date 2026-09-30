# Participant photographs and team logos

## Team logos — 2026-09-30

Wettfinder and Daily3 use the same shield-shaped image slots for all six sports.
Football and tennis keep their existing mappings below. Team logos load directly
in the browser; BetBoy does not download, decode or store image bytes.

- Basketball: ESPN NBA IDs require an explicit NBA competition, including
  namespaced IDs. WNBA/NCAA IDs must never produce NBA logos. Two EuroLeague
  teams currently have explicit reviewed provider-code/name bindings.
- Ice hockey: 32 currently active NHL teams have reviewed native ID/name/logo
  bindings from the official identity catalog. Utah Mammoth is ID 68; inactive
  Utah Hockey Club ID 59 is not reused.
- Cricket: India and Australia currently have exact reviewed country bindings
  for Cricbuzz and CricketData; no country logo is reused for A/youth/women's
  teams or similarly named clubs. These are the provider's national-team flags.
- E-Sport: nine reviewed native PandaScore team/name bindings. The NAVI page's
  `1w` thumbnail was visually a Dota game icon, not a team logo; it was rejected.
  Unknown/unverified squads retain initials, not another team's logo.

The regular E-Sport scanner also remembers only ID/name/logo-link metadata
already present in its successful, in-window responses. No new API call is made.
`runtime_state/participant-logos.json` is bounded to 256 teams / 128 KiB and
deduplicated: identical responses do not rewrite it. Native ID and full name
must agree; only PandaScore's documented 200px `thumb_` raster URLs are used.
It is a small link catalog, not a picture cache or a second sporting database.
Existing model dictionaries, probabilities, hashes, prices and money are unchanged.

`team-logos.json` holds the reviewed source metadata. Logos are fitted without
clipping inside the existing shield; only the official NHL logo SVG path is
allowed as an external `img`, never inline SVG or an embedded document.
Commons PNG thumbnails preserve their author/license link as `© Logo`.
Other sources have exact allowlisted paths or individually reviewed small URLs.
Logo ownership and trademarks remain with their respective owners; no endorsement
or blanket commercial clearance is claimed. New sources require identity and
rights/source verification. Failed/unknown images retain initials.

## Tennis player photographs

`tennis-portraits.json` is an explicit identity allowlist of real photographs, not generated faces or surname-only guesses. The six currently visible players (Rei Sakamoto, Matteo Arnaldi, Arthur Gea, Zhang Zhizhen, Novak Djokovic and Nuno Borges) are covered, alongside other commonly used players.

All entries were checked against Wikimedia Commons file descriptions/categories and the public `imageinfo` API on 2026-09-30. `url` is the official Wikimedia 330 px thumbnail returned for a 320 px API request, with tracking query parameters removed. `file` is a stable manifest label, not a stored image or the Commons filename; `source_file` preserves the exact original file title. The manifest records the named photographer or public creator pseudonym exactly as credited by Commons.

Participant images load directly from the public HTTPS CDN in the customer's browser. BetBoy stores only this small JSON metadata manifest: no image downloads, binary RAM cache, image-file cache or database copies on the server. The browser may use its normal HTTP cache. Portrait URLs must be raster thumbnails no wider than 400 px (current entries: 330 px); club crests use the existing native API-Football team ID. Sources are allowlisted, requests omit the page referrer, and image loading is lazy. Failed or unavailable images show initials in the same shield; source availability is not prechecked by the server. Existing decorative editorial banner assets are separate and unchanged.

The application must retain the `source` link, `credit`, `license_url` and disclosure of display cropping/resizing. CC BY-SA adaptations retain the corresponding same/share-alike license. A photograph's free copyright license is not an endorsement by the athlete and does not remove unrelated personality or trademark rights. Do not present these athletes as endorsing BetBoy.

Matching must use the complete verified names/aliases. Do not identify a player from surname or initials alone. Unknown players keep the honest non-photo fallback until a verified entry is added. Do not reuse another player's face for an unknown name. Remote failures must also keep the fallback rather than a broken image.

No ATP-page scraping, stock-agency image copying, model/API credentials, database changes or generated imagery are involved. Adding a photo requires checking identity, author, license and the concrete image URL on its file page/API first. Public API requests should be batched and rate-limited; metadata errors must never reuse the previous response for a different player.
