import { Bot, Camera, GitPullRequestArrow, PlayCircle, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";

const features = [
  {
    icon: Sparkles,
    title: "AI-generated test cases",
    description:
      "Give TestPilot a URL and it analyzes your pages, identifies key user flows, and generates positive, negative, and edge-case test scenarios — reviewable and editable before anything runs.",
  },
  {
    icon: PlayCircle,
    title: "Real browser execution",
    description:
      "Test cases run as real Playwright-driven browser sessions — clicking, typing, submitting, and asserting exactly like a user would, with full execution logs.",
  },
  {
    icon: Bot,
    title: "AI failure analysis",
    description:
      "When a test fails, get a plain-language explanation, a likely root cause, a severity rating, and a suggested fix — not just a stack trace.",
  },
  {
    icon: Camera,
    title: "Evidence, not guesswork",
    description:
      "Every test run captures screenshots and step-by-step logs, so you can see exactly what happened and why.",
  },
  {
    icon: GitPullRequestArrow,
    title: "Bugs, tracked to resolution",
    description:
      "Turn a failed test straight into a tracked issue, pre-filled with evidence and linked back to the test case and run that found it.",
  },
  {
    icon: ShieldCheck,
    title: "Built for teams",
    description:
      "Every organization's data is isolated from day one, with usage-based plans that grow from a solo project to a full QA team.",
  },
];

export default function LandingPage() {
  return (
    <>
      <section className="mx-auto max-w-4xl px-4 pb-16 pt-20 text-center">
        <h1 className="text-display font-bold tracking-tight text-foreground sm:text-5xl">
          Test your web app with AI, not automation scripts
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-subheading text-muted-foreground">
          Give TestPilot AI a URL. Get AI-generated test cases, real browser-driven test
          execution, and AI-explained failures — in minutes, not sprints.
        </p>
        <div className="mt-8 flex items-center justify-center gap-3">
          <Button asChild size="lg">
            <Link href="/signup">Start testing free</Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="/pricing">See pricing</Link>
          </Button>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 pb-24">
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map((feature) => (
            <Card key={feature.title}>
              <CardHeader>
                <feature.icon className="h-6 w-6 text-primary" aria-hidden="true" />
                <CardTitle>{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-body text-muted-foreground">{feature.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="border-t border-border bg-muted/50">
        <div className="mx-auto max-w-4xl px-4 py-16 text-center">
          <h2 className="text-heading font-semibold text-foreground">
            From URL to tested, in one sitting
          </h2>
          <p className="mx-auto mt-3 max-w-xl text-body text-muted-foreground">
            No dedicated QA team required. Sign up, add your website, and see your first
            AI-generated test cases before your coffee gets cold.
          </p>
          <div className="mt-6">
            <Button asChild size="lg">
              <Link href="/signup">Create your free account</Link>
            </Button>
          </div>
        </div>
      </section>
    </>
  );
}
