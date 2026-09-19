# Load & solar profiles

`timeseries.LOAD_PROFILE` and `timeseries.SOLAR_PROFILE` (used by
`/daily-profile`, see `README.md`) are derived from real interval data,
not hand-shaped curves. This documents exactly what that means and
where it falls short of what a DNSP would actually use.

## LOAD_PROFILE: City East zone substation, Canberra (ACT)

`data/canberra_city_east_2024-25.csv` - real half-hourly MW demand for
City East zone substation, 1 Jul 2024 - 1 Jul 2025 (trimmed from a
larger zone-substation report covering multiple ACT substations - only
the column this project uses is checked in). City East is not a
stand-in: it's the actual substation this project already names as the
feeder's root (`geo.py`'s `DEFAULT_BASE_LAT`/`DEFAULT_BASE_LON`
comment), so this is a genuine match between the profile and the
network it's applied to, not a different region borrowed for
convenience.

## SOLAR_PROFILE: one Ausgrid customer, NSW

`data/ausgrid_solar_home_customer12_2011-2012.csv` - real half-hourly
consumption (GC) and solar generation (GG) for one customer in
[Ausgrid's public "Solar Home Electricity" dataset](https://www.ausgrid.com.au/Industry/Our-Research/Data-to-share/Solar-home-electricity-data)
(300 NSW homes with rooftop PV, Jul 2010 - Jun 2013), mirrored with
attribution from
[pierre-haessig/ausgrid-solar-data](https://github.com/pierre-haessig/ausgrid-solar-data).

Unlike LOAD_PROFILE, this **is** a stand-in from a different region:
City East's own zone-substation feed has no solar/generation column,
only net demand, so there's no real ACT solar-generation data behind
this project at all. This is the best available real solar-generation
shape, not a genuine match for this feeder's region or climate.

## Derivation

`data/derive_profiles.py` computes two things from the same two source
files:
- `LOAD_PROFILE` / `SOLAR_PROFILE` (used by `/daily-profile`): median
  value per hour of day, across the *entire* year - one blended day,
  by design, for the interactive hour-scrubber UI.
- `MONTHLY_LOAD_PROFILE` / `MONTHLY_SOLAR_PROFILE` (used by
  `/annual-profile`): median value per (calendar month, hour of day) -
  12 distinct days, so a real seasonal effect can show up. Normalized
  against one peak across all twelve months, not each month's own peak,
  so a genuinely quieter or stronger month stays genuinely quieter or
  stronger - see `normalize_grid()`.

Either way, the script isn't run by the app; it's a reproducibility
record, and the place to look if you want to regenerate the numbers or
swap either input file.

## What this gets right

- Solar output is genuinely zero overnight and peaks at midday - not
  assumed, measured (`SOLAR_PROFILE[12] == SOLAR_PROFILE[13] == 1.0`,
  zero for hours 0-6 and 18-23).
- LOAD_PROFILE is a genuine feeder-level aggregate (thousands of
  customers' diversified demand), not one household's - and it shows:
  its ratio from trough to peak (0.593 to 1.0, about 1.7x) is much
  flatter than a single customer's (the Ausgrid customer's own
  consumption ranges nearly 3x from trough to peak). That flattening
  is diversity doing exactly what it should, and it's a real
  improvement over an earlier version of this file that used the
  Ausgrid customer's consumption for both load and solar.
- `/annual-profile` genuinely captures Canberra's real seasonal shape,
  not an assumed one: MONTHLY_LOAD_PROFILE peaks in June/July (winter -
  a heating-dominated climate) at the grid's overall maximum, and is
  markedly lower in the summer months, which is the real signature of
  an ACT-like climate, not something hand-tuned to produce that result.

## What this doesn't get right

- **SOLAR_PROFILE is the wrong region.** NSW rooftop solar behavior
  (climate, panel orientation norms, feed-in tariff history) isn't ACT
  rooftop solar behavior. There's no getting around this without a
  real ACT solar dataset, which this project doesn't have - so
  MONTHLY_SOLAR_PROFILE inherits this same region mismatch, even
  though its month-to-month shape is real.
- **No weekday/weekend split.** Both `LOAD_PROFILE` and
  `MONTHLY_LOAD_PROFILE` blend weekdays and weekends into the same
  median.
- **`/annual-profile` samples 12 representative days, not all 8,760
  (or 17,520 half-hourly) hours of the real year.** That's a
  deliberate, documented trade-off (see `timeseries.py`'s docstring)
  for keeping a live API request fast on this project's architecture,
  not a claim that every hour of the year was simulated.
- **EV_PROFILE has no real data behind it at all** - no public dataset
  of home EV charging load was used; it's still a hand-shaped curve,
  and `MONTHLY_EV_PROFILE` just repeats it for every month rather than
  carrying any real seasonal signal (see `timeseries.py`).
