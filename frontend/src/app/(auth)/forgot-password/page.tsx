"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/Button";
import { TextField } from "@/components/form/TextField";
import { apiClient } from "@/lib/api-client";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    try {
      // FR-010: always succeeds regardless of whether the account exists —
      // the UI never branches on the response, only on "request sent."
      await apiClient.post("/auth/forgot-password", { email });
    } finally {
      setSubmitting(false);
      setSubmitted(true);
    }
  }

  if (submitted) {
    return (
      <>
        <h1 className="text-heading font-semibold text-foreground">Check your email</h1>
        <p className="mt-2 text-body text-muted-foreground">
          If an account exists for <strong>{email}</strong>, we&apos;ve sent a link to reset your
          password. It expires in 1 hour.
        </p>
        <Link href="/login" className="mt-6 block text-center text-caption text-primary hover:underline">
          Back to log in
        </Link>
      </>
    );
  }

  return (
    <>
      <h1 className="text-heading font-semibold text-foreground">Reset your password</h1>
      <p className="mt-1 text-body text-muted-foreground">
        Enter your email and we&apos;ll send you a reset link.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Button type="submit" loading={submitting} className="w-full">
          Send reset link
        </Button>
      </form>

      <p className="mt-6 text-center text-caption text-muted-foreground">
        <Link href="/login" className="font-medium text-primary hover:underline">
          Back to log in
        </Link>
      </p>
    </>
  );
}
