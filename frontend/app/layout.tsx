import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Invoice Processing",
  description: "AI-assisted extraction, PO matching, and rule-based decisioning for invoice processing.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <Sidebar />
          <main className="main-content">
            <div className="main-inner">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
