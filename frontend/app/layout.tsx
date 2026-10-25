import type { Metadata } from "next";
import "./globals.css";
import { Nav } from "@/components/Nav";

export const metadata: Metadata = {
  title: "PentestAI — Milestone 1",
  description: "AI penetration-testing platform (mock-data skeleton).",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="layout">
          <Nav />
          <div className="main">{children}</div>
        </div>
      </body>
    </html>
  );
}
