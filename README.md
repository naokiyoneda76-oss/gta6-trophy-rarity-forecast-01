# gta6-trophy-rarity-forecast-01

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/naokiyoneda76-oss/gta6-trophy-rarity-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/naokiyoneda76-oss/gta6-trophy-rarity-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

A dependency-free Python forecaster for the Exophase earn rates of Grand Theft Auto VI's 55 PlayStation 5 trophies. For each trophy, it fits logit earn rate against both log-time and raw hours, shrinking each slope toward its field-wide median. It extrapolates with the transform that has the smaller weighted residual SD, blending that move with the player-count trend when enough player observations are available, and anchors every forecast on the last observed rate. It reports the 5/25/50/75/95% quantiles with spreads that grow with the horizon, the fit residuals and the extrapolation distance — wider upward for rare trophies with headroom to climb, wider downward for common ones exposed to dilution by incoming players.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

---

<sub>Entered on [make.fun](https://make.fun/?ref=dwwxce7w&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
