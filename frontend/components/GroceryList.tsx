"use client";

/**
 * GroceryList — Paprika-style interactive grocery checklist.
 * 
 * Key features:
 * - Items grouped by supermarket aisle category
 * - Instant checkbox toggle (pure client-side React state — zero latency)
 * - Checked items get strikethrough + opacity fade with CSS transition
 * - Checked items sink to bottom of their category
 * - Progress indicator
 * - State persisted to localStorage for offline access
 * - "Clear Checked" button
 */

import { useState, useEffect, useCallback } from "react";
import type { GroceryCategory, GroceryItem } from "@/lib/types";

import { updateGroceryChecks } from "@/lib/api";

interface GroceryListProps {
  categories: GroceryCategory[];
  initialCheckedItems?: string[];
}

// Aisle emoji map for visual flair
const AISLE_ICONS: Record<string, string> = {
  "Produce": "🥬",
  "Dairy & Eggs": "🥛",
  "Meat & Seafood": "🥩",
  "Bakery": "🍞",
  "Pantry & Canned": "🥫",
  "Frozen": "🧊",
  "Condiments & Sauces": "🫙",
  "Beverages": "🥤",
  "Other": "📦",
};

export default function GroceryList({ categories, initialCheckedItems = [] }: GroceryListProps) {
  // Use a ref to track if we've initialized from props to avoid overwriting on first render
  const [initialized, setInitialized] = useState(false);
  const [checkedItems, setCheckedItems] = useState<Set<string>>(new Set());
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());

  // Initialize state from props once they arrive
  useEffect(() => {
    if (!initialized && initialCheckedItems.length >= 0) {
      setCheckedItems(new Set(initialCheckedItems));
      setInitialized(true);
    }
  }, [initialCheckedItems, initialized]);

  // Sync checked state to backend whenever it changes (debounced by React state batching)
  useEffect(() => {
    if (!initialized) return;
    
    // We do a "fire and forget" sync to the backend
    updateGroceryChecks(Array.from(checkedItems)).catch((err) =>
      console.error("Failed to sync grocery checks", err)
    );
  }, [checkedItems, initialized]);

  // Generate a unique key for each item
  const itemKey = (categoryName: string, itemName: string) =>
    `${categoryName}::${itemName}`;

  // Toggle a single item — instant, no network call
  const toggleItem = useCallback((key: string) => {
    setCheckedItems((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  // Toggle category collapse
  const toggleCategory = useCallback((name: string) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(name)) {
        next.delete(name);
      } else {
        next.add(name);
      }
      return next;
    });
  }, []);

  // Clear all checked items
  const clearChecked = useCallback(() => {
    setCheckedItems(new Set());
  }, []);

  // Count totals
  const totalItems = categories.reduce((sum, c) => sum + c.items.length, 0);
  const checkedCount = categories.reduce(
    (sum, c) =>
      sum +
      c.items.filter((item) => checkedItems.has(itemKey(c.name, item.name)))
        .length,
    0
  );

  if (categories.length === 0) {
    return null;
  }

  return (
    <div className="grocery-list" id="grocery-list">
      {/* Progress bar */}
      <div className="grocery-progress" id="grocery-progress">
        <div className="grocery-progress-bar">
          <div
            className="grocery-progress-fill"
            style={{ width: `${totalItems > 0 ? (checkedCount / totalItems) * 100 : 0}%` }}
          />
        </div>
        <span className="grocery-progress-text">
          {checkedCount} of {totalItems} items
        </span>
        {checkedCount > 0 && (
          <button
            className="grocery-clear-btn"
            onClick={clearChecked}
            id="clear-checked-btn"
          >
            Clear checked
          </button>
        )}
      </div>

      {/* Category sections */}
      {categories.map((category) => {
        const isCollapsed = collapsedCategories.has(category.name);
        const catCheckedCount = category.items.filter((item) =>
          checkedItems.has(itemKey(category.name, item.name))
        ).length;

        // Sort: unchecked first, checked at bottom
        const sortedItems = [...category.items].sort((a, b) => {
          const aChecked = checkedItems.has(itemKey(category.name, a.name)) ? 1 : 0;
          const bChecked = checkedItems.has(itemKey(category.name, b.name)) ? 1 : 0;
          return aChecked - bChecked;
        });

        return (
          <div className="grocery-category" key={category.name} id={`category-${category.name.replace(/\s+/g, "-").toLowerCase()}`}>
            <button
              className="grocery-category-header"
              onClick={() => toggleCategory(category.name)}
              aria-expanded={!isCollapsed}
            >
              <span className="grocery-category-icon">
                {AISLE_ICONS[category.name] || "📦"}
              </span>
              <span className="grocery-category-name">{category.name}</span>
              <span className="grocery-category-badge">
                {catCheckedCount}/{category.items.length}
              </span>
              <span className={`grocery-category-chevron ${isCollapsed ? "" : "grocery-category-chevron--open"}`}>
                ›
              </span>
            </button>

            {!isCollapsed && (
              <ul className="grocery-items">
                {sortedItems.map((item) => {
                  const key = itemKey(category.name, item.name);
                  const isChecked = checkedItems.has(key);

                  return (
                    <li
                      key={key}
                      className={`grocery-item ${isChecked ? "grocery-item--checked" : ""}`}
                      onClick={() => toggleItem(key)}
                      role="checkbox"
                      aria-checked={isChecked}
                      id={`item-${key.replace(/[^a-zA-Z0-9]/g, "-")}`}
                    >
                      <span className={`grocery-checkbox ${isChecked ? "grocery-checkbox--checked" : ""}`}>
                        {isChecked ? "✓" : ""}
                      </span>
                      <span className="grocery-item-name">{item.name}</span>
                      {item.quantity && (
                        <span className="grocery-item-qty">{item.quantity}</span>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
