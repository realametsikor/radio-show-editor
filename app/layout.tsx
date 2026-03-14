import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Radio Show Editor — Transform AI Podcasts into Radio Shows",
  description:
    "Upload your AI-generated podcast and transform it into a professional radio show with speaker separation, sound effects, and background music mixing.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen antialiased font-sans">{children}</body>
    </html>
  );
}
