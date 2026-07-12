import type { Metadata } from "next";
import "./globals.css";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "Invoice Processing",
  description: "AI-assisted extraction, PO matching, and rule-based decisioning for invoice processing.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="app-hero">
            <h1>Invoice Processing</h1>
            <p>
              AI-assisted extraction, PO matching, and rule-based decisioning — with the reasoning to back up
              every call.
            </p>
          </header>
          <Nav />
          {children}
        </div>
      </body>
    </html>
  );
}
