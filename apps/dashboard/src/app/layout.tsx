import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Code Reviewer — Enterprise Engineering Quality Platform",
  description: "Cross-file architectural reviews, deterministic security flags, and committable suggestion blocks.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-ground text-ink antialiased selection:bg-accent selection:text-white">
        {children}
      </body>
    </html>
  );
}
