"""Plain-text tip labels for the editorial rail; no changes to the saved tip."""


def _double_chance(side, home, away):
    return {"1X": f"{home} oder Unentschieden", "X2": f"{away} oder Unentschieden",
            "12": "Kein Unentschieden"}.get(side)


def _football_label(spec, selection, home, away):
    # If the saved choice contradicts the catalog, do not silently replace it.
    localized = spec.selection.replace(".", ",")
    if selection not in {spec.selection, localized}:
        return None
    kind, side = spec.kind, spec.side
    team = home if side and side.split("_")[0] == "home" else away
    if kind == "result":
        result = {"home": f"Sieg {home}", "draw": "Unentschieden", "away": f"Sieg {away}"}[side]
        return f"{result} (90 Minuten)"
    if kind == "double_chance":
        return f"{_double_chance(side, home, away)} (90 Minuten)"
    if kind == "btts":
        return f"Beide Teams treffen: {localized}"
    if kind in {"total_range", "team_range"}:
        subject = "Gesamttore im Spiel" if kind == "total_range" else team
        return f"{subject}: {spec.low}–{spec.high} Tore"
    match_units = {"total": "Gesamttore", "corner_total": "Eckbälle", "yellow_total": "Gelbe Karten"}
    if kind in match_units:
        return f"{match_units[kind]} im Spiel: {localized}"
    team_units = {"team_total": "Tore", "team_corners": "Eckbälle", "team_yellow": "gelbe Karten"}
    if kind in team_units:
        return f"{team}: {localized} {team_units[kind]}"
    if kind == "result_total":
        chance, direction = side.split("_")
        result = {"1X": f"{home} verliert nicht", "X2": f"{away} verliert nicht",
                  "12": "Kein Unentschieden"}[chance]
        limit = {"over": "über", "under": "unter"}[direction]
        return f"{result} und im Spiel fallen {limit} {_decimal(spec.threshold)} Tore"
    if kind == "mixed_or":
        result = {"btts_yes_or_over": "Beide Teams treffen", "home_or_over": f"{home} gewinnt",
                  "away_or_over": f"{away} gewinnt"}[side]
        return f"{result} oder im Spiel fallen über {_decimal(spec.threshold)} Tore"
    return None


def _decimal(number):
    return str(number).replace(".", ",")


_SPORT_ALIASES = {"fussball": "football", "eishockey": "ice_hockey", "ice hockey": "ice_hockey",
                  "e-sport": "esports"}

# Public H2H is a different sporting event in each source. Match exact known
# captions on older cards which did not retain a key; never infer a period.
_H2H = {
    "tennis": ("Match Winner", "Sieg {}"),
    "esports": ("Match Winner", "Seriensieg {}"),
    "ice_hockey": ("Sieger inklusive Verlängerung und Penaltyschießen",
                   "Sieg {} (inkl. Verlängerung und Penaltyschießen)"),
    "basketball": ("Sieger inklusive Overtime", "Sieg {} (inkl. Verlängerung)"),
}


def rail_selection_label(*, sport, market_key, selection, home="", away="", market="", selected_competitor="") -> str:
    """Explain one recorded selection. Participants must be native names, not opaque selection keys."""
    selection = (selection or "").strip()
    market = (market or "").strip()
    fallback = " · ".join(dict.fromkeys(value for value in (market, selection) if value))
    caption = market.casefold()
    if caption == "auswahl":  # the public loader's placeholder, not a market
        caption = ""
    sport = (sport or "").strip().casefold()
    sport = _SPORT_ALIASES.get(sport, sport)
    key = (market_key or "").strip().casefold()
    home, away = (home or "").strip(), (away or "").strip()
    if not selection:
        return fallback
    if sport == "football":
        from challenge_engine import MARKET_BY_KEY

        spec = MARKET_BY_KEY.get(key.upper())
        if spec is not None and (not caption or caption == spec.market.casefold()):
            return _football_label(spec, selection, home or "Heimteam", away or "Auswärtsteam") or fallback
    if sport in _H2H and key in {"", "h2h"}:
        source_caption, template = _H2H[sport]
        if caption == source_caption.casefold() or (key == "h2h" and not caption):
            # Some signals already prepend "Sieg"; protect native team names.
            name = selection if selection in (home, away) else selection.removeprefix("Sieg ")
            if home and away:
                bound = (selected_competitor or "").strip()
                if bound and (bound != name or bound not in (home, away)):
                    return "Siegauswahl nicht eindeutig"
                if name not in (home, away):
                    return fallback
            return template.format(name)
    return fallback
