"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Button } from "@/components/Button";
import { TextField } from "@/components/form/TextField";
import { ApiError, useAuth } from "@/lib/auth";

export default function SignupPage() {
  const { signup } = useAuth();
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signup(email, password, name);
      router.push("/overview");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.code === "email_taken") {
          setError("An account with that email already exists.");
        } else if (err.code === "validation_failed") {
          setError("Check your details: password must be at least 10 characters.");
        } else {
          setError(err.message);
        }
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <h1 className="text-heading font-semibold text-foreground">Create your account</h1>
      <p className="mt-1 text-body text-muted-foreground">Start testing in minutes.</p>

      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <TextField
          label="Name"
          type="text"
          autoComplete="name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <TextField
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          label="Password"
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

        <Button type="submit" loading={submitting} className="mt-2 w-full">
          Sign up
        </Button>
      </form>

      <p className="mt-6 text-center text-caption text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Log in
        </Link>
      </p>
    </>
  );
}
