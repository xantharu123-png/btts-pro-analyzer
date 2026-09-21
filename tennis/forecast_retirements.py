"""Explicit operator-approved logical removals, not data or result rewriting.

The four historical WTA lineages were approved for removal on 2026-09-21
after native participant changes made their results unassignable. Exact
publication hashes and parent identities scope this catalog: no event-ID-wide
ban, wildcard, future-forecast suppression, settlement, or model approval.
Reverting the catalog restores active processing; original evidence stays put.
"""
from dataclasses import dataclass
from datetime import datetime


APPROVED_AT = datetime.fromisoformat("2026-09-21T06:07:51+00:00").timestamp()


@dataclass(frozen=True)
class ForecastRetirement:
    event_key: str
    prediction_id: int
    initial_created_utc: float
    original_hashes: frozenset[str]


RETIREMENTS = (
    ForecastRetirement("espn:tennis:WTA:match:183710", 1441, 1789455653.316604, frozenset({
        "a74393fe010813703ffe83049c4a69b8d283aea30fb58cbfe5e6e5d719536628",
        "fda44902b7e8477ab00a90df88fc0f65d1689e08e86a375121a623b193d5b5b0",
    })),
    ForecastRetirement("espn:tennis:WTA:match:183831", 1419, 1789401180.782087, frozenset({
        "0d6a2fabcbf5d7a5d703d478a0a4b9815919f937c9ba43b18c489741bc468d4e",
        "44f868a85dbecb9e8d8e34100fed0932be5dac1b2e308c697cb4f54f42f6459f",
        "ad6b60f42f6264e9c80c26cc96f1eea4e544e0843171c14956c7059ab899723c",
        "d3c69b66d2789d81f45f0a196ea2984c4f52ac8c304fc4d7ed8f5b79850471f8",
        "ed956c0bae9b0f55a8b2ec874800fa130fa4a304cf541732fd232b8fa7e0cde5",
    })),
    ForecastRetirement("espn:tennis:WTA:match:183844", 1414, 1789401180.782087, frozenset({
        "0aae7c5920a408dc3f731f8d8b82868015c1bdababce69c1a946d87b2ca1a5c0",
        "0bd528d5cbf3e7dd8dfa0a93cdc24ba1206fc93fa19086439fc6739338004e97",
        "13246e2ebc3a854076da79942ebef03e2ed421fd2416a418c96df33e27d925db",
        "29b6572c12754608e2f0d5deb7086d2efda1ec1305acedb05adf39b76befde95",
        "2f69693bfd190eab1ff5782a4ea184b897179a6c47428e4efb34cf9795975346",
        "542ccda90d41e013c7d9ef0509536874105c1084a4c98808a614fc7cf54777ef",
        "61a2f5c7166386decb80719f91fcb24d4a77fe79a6867da347657ec5d8a901fc",
        "75d1f3254b458eb4b165f838817fc32e19124ec9ae6130a7f9c0b9a8a1d67eb9",
        "7ecc4b084ae6ffe85e31827286ee219481933084b9f66001a07c58d6f4bc0f2b",
        "8b3cbbd72cfe8720410ec434c759a9e6728b31ee79987a730b6d285519cb0a06",
        "9b80dbdd3749cedb8b806ec5d81cc238a89e5c185bf25f876c1a4e9c8c1fd022",
        "a52368ae5f0884c2fdd5875ccd5f42fec7ae716f043a7f37e6a208b0d87c3efb",
        "aa2a8d1009bcfe544204face8a591db65a104ca761b7ff189bf6608ca763bb90",
        "ab6a6b854e82bc8a3087ffbd22cb64cba0a13f27564a093080d71a6ffa010d0c",
        "b59a118cd0a43c82714a87cf5f85842cd8b20f6cd17bc76e9bed632d5bc2ae2b",
        "b7fdc796a0811aa554d00d3178bbca5bf8ee7dab9a08162868a56cb2323c0286",
        "c8f4389f95f823101c561a8d30bc46ad2597258c257c1a7b512176f059cf02a7",
        "f75b4bf852bcac255faeaa7ab9748c8aa63ebaa2f3c6d0d4c5d1b92796b28554",
    })),
    ForecastRetirement("espn:tennis:WTA:match:183854", 1409, 1789401180.782087, frozenset({
        "45d098a20e37e06e5558497b52e94917e4f5e198000320c4622d0d107bfab7a4",
        "77110163c447a8a59c0af36011e92dfc0730daad229b1fcafce98a185ccee7bc",
        "7c5f8becae5349454a35aa1e258b9eeae7808b28f85e578b00e8d265971e8f1b",
        "a14f683e682e379cdb3ee7d3db533041b0253cb39e82682c8e856590f55b65f7",
        "d9ddc0cabe05395a202cbbd3e1e5fc56d734effe881928966a85c638405ec212",
    })),
)


def original_is_retired(reference: str, event_key: str) -> bool:
    """Called only AFTER the owning reader validates the actual original."""
    return any(item.event_key == event_key and reference in item.original_hashes
               for item in RETIREMENTS)


def prediction_is_retired(row, *, as_of: float | None = None) -> bool:
    if as_of is not None and as_of < APPROVED_AT:
        return False
    if row.get("fixture_source") != "ESPN" or type(row.get("id")) is not int:
        return False
    event_key = f"espn:tennis:{row.get('tour')}:match:{row.get('provider_event_id')}"
    created = row.get("initial_created_utc", row.get("created_utc"))
    return any(item.event_key == event_key and item.prediction_id == row["id"]
               and item.initial_created_utc == created for item in RETIREMENTS)
