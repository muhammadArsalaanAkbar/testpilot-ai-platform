"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { Button } from "@/components/Button";
import { TextField } from "@/components/form/TextField";
import { apiClient, ApiError } from "@/lib/api-client";

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setError(null);
    setSubmitting(true);
    try {
      await apiClient.post("/auth/reset-password", { token, new_password: password });
      setSuccess(true);
    } catch (err) {
      if (err instanceof ApiError && err.code === "invalid_or_expired_token") {
        setError("This reset link is invalid or has expired. Request a new one.");
      } else if (err instanceof ApiError && err.code === "validation_failed") {
        setError("Password must be at least 10 characters.");
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (!token) {
    return (
      <>
        <h1 className="text-heading font-semibold text-foreground">Invalid reset link</h1>
        <p className="mt-2 text-body text-muted-foreground">
          This link is missing its reset token. Request a new one below.
        </p>
        <Link
          href="/forgot-password"
          className="mt-6 block text-center text-caption text-primary hover:underline"
        >
          Request a new link
        </Link>
      </>
    );
  }

  if (success) {
    return (
      <>
        <h1 className="text-heading font-semibold text-foreground">Password updated</h1>
        <p className="mt-2 text-body text-muted-foreground">
          Your password has been changed. You can now log in with your new password.
        </p>
        <Button asChild className="mt-6 w-full">
          <Link href="/login">Log in</Link>
        </Button>
      </>
    );
  }

  return (
    <>
      <h1 className="text-heading font-semibold text-foreground">Set a new password</h1>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          required
          hint="At least 10 characters"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        {error && (
          <p role="alert" className="text-caption text-destructive">
            {error}
          </p>
        )}

        <Button type="submit" loading={submitting} className="w-full">
          Update password
        </Button>
      </form>
    </>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
