import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Rail } from "@/components/Rail";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  variable: "--font-jetbrains",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Genome Firewall",
  description:
    "Genome-based antibiotic susceptibility prediction with calibrated abstention — and a refusal to guess when it shouldn't.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrains.variable} h-full antialiased`}>
      <body className="min-h-full">
        <Rail />
        <main className="ml-[230px] min-h-screen px-8 py-7">
          <div className="mx-auto max-w-[1240px]">{children}</div>
        </main>
      </body>
    </html>
  );
}
