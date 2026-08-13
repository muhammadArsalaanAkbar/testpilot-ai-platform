import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider, themeInitScript } from "@/lib/theme-provider";
import { AppQueryProvider } from "@/lib/query-client";
import { AuthProvider } from "@/lib/auth";
import { TooltipProvider } from "@/components/Tooltip";
import { ToastRootProvider } from "@/components/Toast";

export const metadata: Metadata = {
  title: "TestPilot AI",
  description: "AI-powered web application testing platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <ThemeProvider>
          <AppQueryProvider>
            <AuthProvider>
              <TooltipProvider>
                <ToastRootProvider>{children}</ToastRootProvider>
              </TooltipProvider>
            </AuthProvider>
          </AppQueryProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
