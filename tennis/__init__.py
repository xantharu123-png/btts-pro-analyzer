"""Tennis prediction package.

Phase 1: historical training + walk-forward backtest.
Data planes (same architecture as the football pipeline):

- STATS plane (odds-blind): ManTennisData ATP serve/return statistics.
- ODDS plane (evaluation only): tennis-data.co.uk Pinnacle/Bet365
  closing prices.  Only the backtest may read this plane.

Markets modelled by the exact point->game->set->match simulator:
match winner, set totals (e.g. over 3.5 sets in Bo5), game totals,
game handicaps, correct set scores, tiebreak-in-match.
"""
