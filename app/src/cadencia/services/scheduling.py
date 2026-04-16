import calendar
from datetime import date, timedelta


def next_expected_one_on_one(
    last_date: date,
    cadence_days: int,
    weekday: int | None = None,
    week_of_month: int | None = None,
) -> date:
    """Compute the next expected 1:1 date from the last one.

    weekday: 0=Mon .. 6=Sun
    week_of_month: 1-4 or -1 (last). Only used when weekday is also set and cadence >= 28.
    """
    if weekday is None:
        return last_date + timedelta(days=cadence_days)

    if week_of_month is not None:
        # Monthly ordinal pattern, e.g. "3rd Thursday each month"
        target = last_date + timedelta(days=max(cadence_days - 7, 1))
        result = _nth_weekday_of_month(target.year, target.month, weekday, week_of_month)
        if result <= last_date:
            if target.month == 12:
                result = _nth_weekday_of_month(target.year + 1, 1, weekday, week_of_month)
            else:
                result = _nth_weekday_of_month(
                    target.year, target.month + 1, weekday, week_of_month
                )
        return result

    # Interval-based pattern, e.g. "every other Thursday"
    raw = last_date + timedelta(days=cadence_days)
    delta = (weekday - raw.weekday()) % 7
    if delta > 3:
        delta -= 7
    result = raw + timedelta(days=delta)
    if result <= last_date:
        result += timedelta(days=7)
    return result


def _nth_weekday_of_month(year: int, month: int, weekday: int, week: int) -> date:
    if week == -1:
        last_day = calendar.monthrange(year, month)[1]
        d = date(year, month, last_day)
        while d.weekday() != weekday:
            d -= timedelta(days=1)
        return d
    first = date(year, month, 1)
    delta = (weekday - first.weekday()) % 7
    first_occurrence = first + timedelta(days=delta)
    return first_occurrence + timedelta(weeks=week - 1)
