import type { Metadata, Viewport } from "next";
import { Archivo, Spline_Sans_Mono } from "next/font/google";
import "./globals.css";

const archivo = Archivo({ subsets: ["latin"], axes: ["wdth"], variable: "--font-archivo", display: "swap" });
const splineMono = Spline_Sans_Mono({ subsets: ["latin"], variable: "--font-spline-mono", display: "swap" });

export const metadata: Metadata = {
  title: { default: "DFU-WoundMonitor", template: "%s · DFU-WoundMonitor" },
  description: "A research prototype that reads a photo against nine checks before it measures anything.",
};

export const viewport: Viewport = { themeColor: "#2a1530" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${archivo.variable} ${splineMono.variable} antialiased`}>
      <body>{children}</body>
    </html>
  );
}
