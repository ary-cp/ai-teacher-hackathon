import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Teacher — a teacher, not a chatbot",
  description:
    "Personalized AI educator: understands your material, plans a lesson, teaches with voice and visuals, questions you, and adapts when you get it wrong.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background">{children}</body>
    </html>
  );
}
