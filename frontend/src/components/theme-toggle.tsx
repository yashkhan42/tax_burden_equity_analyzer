"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const controlLabel =
    resolvedTheme === "light" ? "Use dark mode" : "Use light mode";

  return (
    <Button
      aria-label={controlLabel}
      className="theme-toggle"
      onClick={() => setTheme(resolvedTheme === "light" ? "dark" : "light")}
      size="icon"
      title={controlLabel}
      type="button"
      variant="ghost"
    >
      <Sun aria-hidden="true" className="theme-icon theme-icon-sun" size={18} />
      <Moon
        aria-hidden="true"
        className="theme-icon theme-icon-moon"
        size={18}
      />
    </Button>
  );
}
