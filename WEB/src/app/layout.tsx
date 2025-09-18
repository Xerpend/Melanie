import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "Melanie AI Assistant",
  description: "Your intelligent assistant for coding, research, and creative tasks",
  keywords: ["AI", "assistant", "coding", "research", "chat"],
  authors: [{ name: "Melanie AI Team" }],
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#001F3F",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full">
      <body
        className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
