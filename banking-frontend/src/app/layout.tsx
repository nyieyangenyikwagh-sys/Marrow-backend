import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "Morrow | Your money, in your hands",
  description: "Your everyday banking, together in one place.",
};
export default function Layout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
