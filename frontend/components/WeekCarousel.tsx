"use client";

/**
 * WeekCarousel — previous/next week navigation with current week display.
 */

import { shiftWeek } from "@/lib/dateUtils";

interface WeekCarouselProps {
  weekStart: string; // YYYY-MM-DD
  onWeekChange: (newWeekStart: string) => void;
}

function formatWeekLabel(dateStr: string): string {
  const d = new Date(dateStr + "T00:00:00");
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export default function WeekCarousel({ weekStart, onWeekChange }: WeekCarouselProps) {
  return (
    <div className="week-carousel" id="week-carousel">
      <button
        className="week-carousel-btn"
        onClick={() => onWeekChange(shiftWeek(weekStart, -1))}
        aria-label="Previous week"
        id="prev-week-btn"
      >
        ◀
      </button>
      <h2 className="week-carousel-label">
        Week of {formatWeekLabel(weekStart)}
      </h2>
      <button
        className="week-carousel-btn"
        onClick={() => onWeekChange(shiftWeek(weekStart, 1))}
        aria-label="Next week"
        id="next-week-btn"
      >
        ▶
      </button>
    </div>
  );
}
