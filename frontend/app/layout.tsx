import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AstraCortex OS",
  description: "Cognitive Operating System — plan, act, remember, reflect",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
