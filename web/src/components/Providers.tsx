"use client";

import { ThemeProvider } from "next-themes";

/**
 * Client component wrapper for context providers.
 * Required because layout.tsx is a Server Component.
 */
export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      storageKey="compta-ecom-theme"
    >
      {children}
    </ThemeProvider>
  );
}
