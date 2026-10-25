import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/Nav";

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
  fallback: ["Segoe UI Variable Text", "Segoe UI", "system-ui", "sans-serif"],
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono-face",
  display: "swap",
  fallback: ["Cascadia Mono", "Consolas", "monospace"],
});

export const metadata: Metadata = {
  title: "AI Pentest — Security Platform",
  description:
    "AI-assisted penetration testing and remediation. Real scanners, verified evidence, human-controlled fixes.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body>
        <div className="layout">
          <Nav />
          <div className="main">{children}</div>
        </div>
      </body>
    </html>
  );
}
