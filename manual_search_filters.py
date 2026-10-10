"""Read-only presentation filters; probabilities and market prices stay separate."""
from dataclasses import dataclass
import math
from numbers import Real


def _number(value):
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    return float(value) if math.isfinite(value) else None


@dataclass(frozen=True)
class SearchFilters:
    probability_min: float = 0.0
    probability_max: float = 1.0
    quote_min: float | None = None
    quote_max: float | None = None
    market_kind: str | frozenset[str] | None = None

    def __post_init__(self):
        low, high = _number(self.probability_min), _number(self.probability_max)
        if low is None or high is None or not 0 <= low <= high <= 1:
            raise ValueError("Wahrscheinlichkeit: Von muss zwischen 0 und Bis liegen (maximal 100 %).")
        for value in (self.quote_min, self.quote_max):
            if value is not None and (_number(value) is None or value < 1.20):
                raise ValueError("Quoten müssen mindestens 1,20 betragen.")
        if self.quote_min is not None and self.quote_max is not None and self.quote_min > self.quote_max:
            raise ValueError("Quote: Von darf nicht höher als Bis sein.")

    @property
    def probability_active(self):
        return self.probability_min != 0 or self.probability_max != 1

    @property
    def quote_active(self):
        return self.quote_min is not None or self.quote_max is not None

    def matches(self, *, probability, quote=None, market_kind=None):
        if self.market_kind is not None:
            kinds = self.market_kind if isinstance(self.market_kind, frozenset) else (self.market_kind,)
            if market_kind not in kinds:
                return False
        if probability is None:
            if self.probability_active:
                return False
        else:
            chance = _number(probability)
            if chance is None or not 0 <= chance <= 1:
                return False
            # 1 - .42 is .5800000000000001 in binary floating point. Only
            # the boundary comparison tolerates machine precision; no model
            # value is rounded or replaced.
            if ((chance < self.probability_min and not math.isclose(chance, self.probability_min, rel_tol=0, abs_tol=1e-12))
                    or (chance > self.probability_max and not math.isclose(chance, self.probability_max, rel_tol=0, abs_tol=1e-12))):
                return False
        price = _number(quote)
        if quote is not None and (price is None or price < 1.20):
            return False
        if price is None:
            return not self.quote_active
        return ((self.quote_min is None or price >= self.quote_min)
                and (self.quote_max is None or price <= self.quote_max))


def render_search_filters(st, *, key_prefix, market_kind=None):
    """Visible controls only: no cache writes, network calls or model run."""
    with st.container(key=key_prefix):
        probabilities = st.slider("Modellwahrscheinlichkeit (%)", 0, 100, (0, 100),
                                  step=1, key=key_prefix + "_probability")
        quote_min = quote_max = None
        if st.checkbox("Nach Quote filtern", value=False, key=key_prefix + "_quote_enabled"):
            columns = st.columns(2)
            with columns[0]:
                quote_min = st.number_input("Quote von", min_value=1.20, value=1.20,
                                            step=.05, format="%.2f", key=key_prefix + "_quote_min")
            with columns[1]:
                quote_max = st.number_input("Quote bis", min_value=1.20, value=10.00,
                                            step=.05, format="%.2f", key=key_prefix + "_quote_max")
        try:
            return SearchFilters(probability_min=probabilities[0] / 100,
                                 probability_max=probabilities[1] / 100,
                                 quote_min=quote_min, quote_max=quote_max,
                                 market_kind=market_kind)
        except ValueError as exc:
            st.error(str(exc))
            st.stop()
