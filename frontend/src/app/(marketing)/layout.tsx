import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/Button";

export const metadata: Metadata = {
  title: {
    default: "TestPilot AI — AI-Powered Web Application Testing",
    template: "%s — TestPilot AI",
  },
  description:
    "Point TestPilot AI at your website and get AI-generated test cases, real browser-driven test execution, and AI-explained failure analysis — no automation scripts required.",
  openGraph: {
    title: "TestPilot AI — AI-Powered Web Application Testing",
    description:
      "AI-generated test cases, real browser test execution, and AI-explained failures — from a URL, in minutes.",
    type: "website",
    siteName: "TestPilot AI",
  },
  twitter: {
    card: "summary_large_image",
    title: "TestPilot AI — AI-Powered Web Application Testing",
    description:
      "AI-generated test cases, real browser test execution, and AI-explained failures — from a URL, in minutes.",
  },
};

const navLinks = [{ href: "/pricing", label: "Pricing" }];

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-border">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4">
          <Link href="/" className="text-subheading font-semibold text-foreground">
            TestPilot AI
          </Link>
          <nav aria-label="Marketing" className="hidden items-center gap-6 md:flex">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-body text-muted-foreground hover:text-foreground"
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <Button asChild variant="ghost" size="sm">
              <Link href="/login">Log in</Link>
            </Button>
            <Button asChild size="sm">
              <Link href="/signup">Sign up</Link>
            </Button>
          </div>
        </div>
      </header>

      <main className="flex-1">{children}</main>

      <footer className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 py-8 text-caption text-muted-foreground md:flex-row">
          <span>© {new Date().getFullYear()} TestPilot AI. All rights reserved.</span>
          <nav aria-label="Footer" className="flex items-center gap-4">
            <Link href="/pricing" className="hover:text-foreground">
              Pricing
            </Link>
            <Link href="/login" className="hover:text-foreground">
              Log in
            </Link>
            <Link href="/signup" className="hover:text-foreground">
              Sign up
            </Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
