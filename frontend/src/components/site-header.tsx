"use client";

import { Menu, X } from "lucide-react";
import { motion, useScroll } from "framer-motion";
import { useEffect, useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const links = [
  { href: "#argument", label: "Argument" },
  { href: "#analyze", label: "Analyze" },
  { href: "#evidence", label: "Evidence" },
  { href: "#method", label: "Method" },
];

export function SiteHeader() {
  const [compact, setCompact] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const { scrollYProgress } = useScroll();

  useEffect(() => {
    const onScroll = () => setCompact(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!menuOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMenuOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [menuOpen]);

  return (
    <header className={cn("site-header", compact && "site-header-compact")}>
      <div className="site-header-inner">
        <a className="site-name" href="#top" onClick={() => setMenuOpen(false)}>
          Tax burden equity analyzer
        </a>
        <nav aria-label="Main navigation" className="desktop-nav">
          {links.map((link) => (
            <a href={link.href} key={link.href}>
              {link.label}
            </a>
          ))}
        </nav>
        <div className="header-actions">
          <ThemeToggle />
          <Button
            aria-expanded={menuOpen}
            aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            className="menu-button"
            onClick={() => setMenuOpen((open) => !open)}
            size="icon"
            type="button"
            variant="ghost"
          >
            {menuOpen ? <X aria-hidden size={20} /> : <Menu aria-hidden size={20} />}
          </Button>
        </div>
      </div>
      <nav
        aria-label="Mobile navigation"
        aria-hidden={!menuOpen}
        className={cn("mobile-nav", menuOpen && "mobile-nav-open")}
      >
        {links.map((link) => (
          <a
            href={link.href}
            key={link.href}
            onClick={() => setMenuOpen(false)}
            tabIndex={menuOpen ? 0 : -1}
          >
            {link.label}
          </a>
        ))}
      </nav>
      <motion.div
        aria-hidden="true"
        className="scroll-progress"
        style={{ scaleX: scrollYProgress }}
      />
    </header>
  );
}
