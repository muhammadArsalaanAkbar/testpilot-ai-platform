import type { Metadata } from "next";
import { Check } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { ErrorState } from "@/components/states/ErrorState";

export const metadata: Metadata = {
  title: "Pricing",
  description: "TestPilot AI plans and pricing — from a free tier to full team plans.",
};

interface PlanLimits {
  max_projects: number | null;
  max_test_executions_per_period: number | null;
  max_ai_operations_per_period: number | null;
  max_members: number | null;
}

interface Plan {
  tier: "free" | "starter" | "professional" | "enterprise";
  limits: PlanLimits;
  price_cents: number | null;
}

interface PlansResponse {
  items: Plan[];
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function fetchPlans(): Promise<Plan[] | null> {
  try {
    const res = await fetch(`${API_BASE_URL}/billing/plans`, {
      // Plan catalog changes rarely; a short revalidation window keeps the
      // marketing page fast without ever showing badly stale pricing.
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    const data = (await res.json()) as PlansResponse;
    return data.items;
  } catch {
    return null;
  }
}

function formatLimit(value: number | null): string {
  return value === null ? "Unlimited" : value.toLocaleString();
}

function formatPrice(cents: number | null): string {
  if (cents === null) return "Contact us";
  if (cents === 0) return "$0";
  return `$${(cents / 100).toLocaleString()}`;
}

const tierLabels: Record<Plan["tier"], string> = {
  free: "Free",
  starter: "Starter",
  professional: "Professional",
  enterprise: "Enterprise",
};

export default async function PricingPage() {
  const plans = await fetchPlans();

  return (
    <div className="mx-auto max-w-6xl px-4 py-16">
      <div className="text-center">
        <h1 className="text-display font-bold text-foreground">Plans that grow with your team</h1>
        <p className="mx-auto mt-3 max-w-xl text-body text-muted-foreground">
          Start free. Upgrade when you need more projects, more test executions, or more AI
          operations per month.
        </p>
      </div>

      {!plans ? (
        <div className="mt-12">
          <ErrorState
            variant="unavailable"
            title="Pricing is temporarily unavailable"
            description="We couldn't reach the billing service. Please try again shortly."
          />
        </div>
      ) : (
        <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {plans.map((plan) => (
            <Card key={plan.tier} className="flex flex-col">
              <CardHeader>
                <CardTitle>{tierLabels[plan.tier]}</CardTitle>
                <p className="text-display font-bold text-foreground">
                  {formatPrice(plan.price_cents)}
                  {plan.price_cents !== null && plan.price_cents > 0 && (
                    <span className="text-caption font-normal text-muted-foreground">/mo</span>
                  )}
                </p>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-3">
                <ul className="flex flex-1 flex-col gap-2 text-body text-muted-foreground">
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                    {formatLimit(plan.limits.max_projects)} projects
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                    {formatLimit(plan.limits.max_test_executions_per_period)} test executions/mo
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                    {formatLimit(plan.limits.max_ai_operations_per_period)} AI operations/mo
                  </li>
                  <li className="flex items-center gap-2">
                    <Check className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
                    {formatLimit(plan.limits.max_members)} team members
                  </li>
                </ul>
                <Button asChild className="mt-2 w-full">
                  <Link href="/signup">Get started</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
