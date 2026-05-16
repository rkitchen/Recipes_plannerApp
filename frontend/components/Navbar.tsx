"use client";

/**
 * Navbar — fixed bottom tab bar for mobile-first navigation.
 * Three tabs: Meals, Grocery, Profile.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { href: "/", label: "Meals", icon: "🍽️" },
  { href: "/grocery", label: "Grocery", icon: "🛒" },
  { href: "/profile", label: "Profile", icon: "👤" },
];

export default function Navbar() {
  const pathname = usePathname();

  // Don't show navbar on login page
  if (pathname === "/login") return null;

  return (
    <nav className="navbar" id="main-navbar">
      {tabs.map((tab) => {
        const isActive = pathname === tab.href;
        return (
          <Link
            key={tab.href}
            href={tab.href}
            className={`navbar-tab ${isActive ? "navbar-tab--active" : ""}`}
            id={`nav-${tab.label.toLowerCase()}`}
          >
            <span className="navbar-icon">{tab.icon}</span>
            <span className="navbar-label">{tab.label}</span>
            {isActive && <span className="navbar-indicator" />}
          </Link>
        );
      })}
    </nav>
  );
}
