import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpenSync",
  description:
    "A contribution readiness engine. Find OSS repos you're ready for, matched to where you want to grow.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        {children}
      </body>
    </html>
  );
}