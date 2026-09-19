"""
Derives LOAD_PROFILE / SOLAR_PROFILE in timeseries.py from real interval
data instead of hand-shaped curves.
"""
import csv
from pathlib import Path

SOLAR_CSV_PATH = Path(__file__).parent / "ausgrid_solar_home_customer12_2011-2012.csv"
LOAD_CSV_PATH = Path(__file__).parent / "canberra_city_east_2024-25.csv"


def _hourly_medians_from_ausgrid_solar():
    """Median GG (solar generation, kWh/half-hour) for each hour of
    the day, across the full year - 24 values, from the 48 half-hourly
    readings per day. (This file also has a GC/consumption column, but
    nothing uses it - LOAD_PROFILE comes from the Canberra data below.)"""
    by_hour = {h: [] for h in range(24)}

    with open(SOLAR_CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            hour = int(row[""].split(" ")[1].split(":")[0])
            by_hour[hour].append(float(row["GG"]))

    return {h: median(v) for h, v in by_hour.items()}


def _hourly_medians_from_canberra():
    """Median City East demand (MW) for each hour of the day, across
    the full 2024-25 year, from the 48 half-hourly readings per day."""
    by_hour = {h: [] for h in range(24)}

    with open(LOAD_CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row["City East"]:
                continue  # a handful of missing readings in the source file
            hour = int(row["DateTime"].split(" ")[1].split(":")[0])
            by_hour[hour].append(float(row["City East"]))

    return {h: median(v) for h, v in by_hour.items()}


def _monthly_medians_from_canberra():
    """Real City East demand (MW), grouped by (calendar month, hour of
    day) - 12 x 24 medians, from the same half-hourly readings."""
    by_month_hour = {m: {h: [] for h in range(24)} for m in range(1, 13)}
    with open(LOAD_CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row["City East"]:
                continue
            date_part, time_part = row["DateTime"].split(" ")
            month, hour = int(date_part.split("-")[1]), int(time_part.split(":")[0])
            by_month_hour[month][hour].append(float(row["City East"]))
    return {m: {h: median(v) for h, v in hours.items()} for m, hours in by_month_hour.items()}


def _monthly_medians_from_ausgrid_solar():
    """Real Ausgrid customer solar generation (GG), same grouping."""
    by_month_hour = {m: {h: [] for h in range(24)} for m in range(1, 13)}
    with open(SOLAR_CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_part, time_part = row[""].split(" ")
            month, hour = int(date_part.split("-")[1]), int(time_part.split(":")[0])
            by_month_hour[month][hour].append(float(row["GG"]))
    return {m: {h: median(v) for h, v in hours.items()} for m, hours in by_month_hour.items()}


def normalize_grid(by_month_hour):
    """Normalize a {month: {hour: value}} grid against ONE peak across
    the whole grid - not each month's own peak - so real seasonal
    amplitude differences (e.g. more solar output in summer) survive
    normalization instead of being flattened away. Returns a 12x24
    list, months 1-12 in order."""
    peak = max(by_month_hour[m][h] for m in by_month_hour for h in by_month_hour[m])
    return [[round(by_month_hour[m][h] / peak, 3) for h in range(24)] for m in range(1, 13)]


def median(values):
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def normalize(by_hour):
    peak = max(by_hour.values())
    return [round(by_hour[h] / peak, 3) for h in range(24)]


if __name__ == "__main__":
    solar = _hourly_medians_from_ausgrid_solar()
    load = _hourly_medians_from_canberra()
    print("LOAD_PROFILE =", normalize(load))
    print("SOLAR_PROFILE =", normalize(solar))
    print()
    print("MONTHLY_LOAD_PROFILE =")
    for row in normalize_grid(_monthly_medians_from_canberra()):
        print(f"    {row},")
    print()
    print("MONTHLY_SOLAR_PROFILE =")
    for row in normalize_grid(_monthly_medians_from_ausgrid_solar()):
        print(f"    {row},")
