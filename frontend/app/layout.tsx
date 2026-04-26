import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PortfolioIQ — AI Financial Advisor",
  description: "Multi-agent financial advisor with bull/bear debates, live news analysis, and ML predictions.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="h-full">
      <body className="h-full bg-[#0d0d1a] text-gray-100 antialiased">{children}</body>
    </html>
  );
}
