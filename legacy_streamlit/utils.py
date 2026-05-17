from datetime import datetime, timedelta

def get_target_week() -> str:
    """
    Mon-Fri: returns this week's Monday.
    Sat-Sun: returns next week's Monday.
    Returned as YYYY-MM-DD string.
    """
    today = datetime.now()
    if today.weekday() >= 5:  # 5=Sat, 6=Sun
        days_ahead = 7 - today.weekday() 
        target = today + timedelta(days=days_ahead)
    else:
        target = today - timedelta(days=today.weekday())
    return target.strftime("%Y-%m-%d")


def shift_week(current_monday_str: str, weeks: int) -> str:
    """Shift a YYYY-MM-DD date by N weeks."""
    dt = datetime.strptime(current_monday_str, "%Y-%m-%d")
    new_dt = dt + timedelta(weeks=weeks)
    return new_dt.strftime("%Y-%m-%d")
