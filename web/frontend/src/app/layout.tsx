import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Trade Copier",
  description: "MT5 Trade Copier Terminal Management",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <nav className="border-b">
          <div className="container mx-auto flex h-14 items-center gap-6 px-4">
            <span className="font-bold">Trade Copier</span>
            <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">Dashboard</Link>
            <Link href="/settings" className="text-sm text-muted-foreground hover:text-foreground">Settings</Link>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
