from datetime import date, datetime, timezone

from date_context import (
    calendar_date,
    german_date_window,
    german_day_label,
    zurich_today,
)


def test_zurich_today_uses_zurich_calendar_boundary():
    before_midnight_utc = datetime(2030, 1, 1, 22, 59, tzinfo=timezone.utc)
    after_midnight_local = datetime(2030, 1, 1, 23, 1, tzinfo=timezone.utc)

    assert zurich_today(before_midnight_utc) == date(2030, 1, 1)
    assert zurich_today(after_midnight_local) == date(2030, 1, 2)


def test_calendar_date_rejects_datetimes_and_invalid_values():
    assert calendar_date("2030-01-02") == date(2030, 1, 2)
    assert calendar_date(date(2030, 1, 2)) == date(2030, 1, 2)
    assert calendar_date(datetime(2030, 1, 2, 12, 0)) is None
    assert calendar_date("not-a-date") is None


def test_german_day_labels_and_windows_share_the_same_reference_day():
    today = date(2030, 1, 1)

    assert german_day_label("2030-01-01", today=today) == "Heute"
    assert german_day_label("2030-01-02", today=today) == "Morgen"
    assert german_day_label("2030-01-04", today=today) == "Am 04.01.2030"
    assert (
        german_date_window("2030-01-01", 7, today=today)
        == "Heute (01.01.2030) bis 08.01.2030"
    )
    assert german_date_window("invalid", 7, today=today) == "unbekannt"
