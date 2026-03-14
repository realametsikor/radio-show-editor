import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Radio Show Editor",
  description:
    "AI-powered radio show editor — separate speakers, add sound effects, and mix background music automatically.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
