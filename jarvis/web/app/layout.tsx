import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "Jarvis",
  description: "Jarvis the Trader",
};

export const viewport: Viewport = {
  themeColor: "#05070B",
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="sv">
      <body>{children}</body>
    </html>
  );
}
