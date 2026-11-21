# gta6-trophy-rarity-forecast-01

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/naokiyoneda76-oss/gta6-trophy-rarity-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/naokiyoneda76-oss/gta6-trophy-rarity-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

A dependency-free Python forecaster for the Exophase earn rates of Grand Theft Auto VI's 55 PlayStation 5 trophies. For each trophy, it recency-weights observations with a 48-hour half-life, then fits logit earn rate against both log-time and raw hours, shrinking each slope toward its field-wide median. When enough observations are available, it averages the selected rate-space move with a decomposition based on estimated earners per player, then blends with the player-count trend. A saturating ceiling curve is also evaluated using at most 48 evenly sampled points for speed; when it fits better than the selected rate-space line, its move replaces the rate move and is damped by 0.55. Otherwise, linear-time and log-time moves are damped by 0.85 and 0.35 respectively. Forecasts remain anchored on the last observed rate, and the spread is scaled by 0.65 because the raw spread was over-wide against known-answer synthetic scenarios. It reports the 5/25/50/75/95% quantiles with spreads that grow with the horizon, the fit residuals and the extrapolation distance — wider upward for rare trophies with headroom to climb, wider downward for common ones exposed to dilution by incoming players.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=dwwxce7w&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
