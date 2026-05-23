/**
 * Date utilities for local date manipulation without timezone offset shifting.
 */

/**
 * Formats a Date object to a YYYY-MM-DD string in the local timezone.
 */
export function formatLocalDate(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/**
 * Returns the YYYY-MM-DD start of the week (Monday) for the given date.
 * If the date is Saturday or Sunday, returns the next Monday.
 */
export function getTargetWeek(date: Date = new Date()): string {
  const day = date.getDay(); // 0=Sun, 1=Mon, ..., 6=Sat
  const target = new Date(date);
  if (day === 0 || day === 6) {
    // Weekend: show next Monday
    const daysAhead = day === 0 ? 1 : 2;
    target.setDate(date.getDate() + daysAhead);
  } else {
    // Weekday: show this Monday
    target.setDate(date.getDate() - (day - 1));
  }
  return formatLocalDate(target);
}

/**
 * Shifts a YYYY-MM-DD date string by a number of weeks, returning YYYY-MM-DD in local time.
 */
export function shiftWeek(dateStr: string, weeks: number): string {
  const d = new Date(dateStr + "T00:00:00");
  d.setDate(d.getDate() + weeks * 7);
  return formatLocalDate(d);
}
