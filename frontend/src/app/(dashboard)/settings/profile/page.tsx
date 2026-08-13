"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/Card";
import { TextField } from "@/components/form/TextField";
import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth";
import { useToast } from "@/components/Toast";

export default function ProfileSettingsPage() {
  const { user, refreshMe } = useAuth();
  const { showToast } = useToast();

  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [profileError, setProfileError] = useState<string | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [changingPassword, setChangingPassword] = useState(false);

  async function handleProfileSubmit(event: FormEvent) {
    event.preventDefault();
    setProfileError(null);
    setSavingProfile(true);
    try {
      await apiClient.patch("/auth/me", { name, email });
      await refreshMe();
      showToast({ variant: "success", title: "Profile updated" });
    } catch (err) {
      if (err instanceof ApiError && err.code === "email_taken") {
        setProfileError("An account with that email already exists.");
      } else {
        setProfileError("Something went wrong. Please try again.");
      }
    } finally {
      setSavingProfile(false);
    }
  }

  async function handlePasswordSubmit(event: FormEvent) {
    event.preventDefault();
    setPasswordError(null);
    setChangingPassword(true);
    try {
      await apiClient.post("/auth/me/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      showToast({ variant: "success", title: "Password updated" });
    } catch (err) {
      if (err instanceof ApiError && err.code === "invalid_current_password") {
        setPasswordError("Current password is incorrect.");
      } else if (err instanceof ApiError && err.code === "validation_failed") {
        setPasswordError("New password must be at least 10 characters.");
      } else {
        setPasswordError("Something went wrong. Please try again.");
      }
    } finally {
      setChangingPassword(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleProfileSubmit} className="flex flex-col gap-4">
            <TextField label="Name" required value={name} onChange={(e) => setName(e.target.value)} />
            <TextField
              label="Email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            {profileError && (
              <p role="alert" className="text-caption text-destructive">
                {profileError}
              </p>
            )}
            <Button type="submit" loading={savingProfile} className="self-start">
              Save changes
            </Button>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handlePasswordSubmit} className="flex flex-col gap-4">
            <TextField
              label="Current password"
              type="password"
              autoComplete="current-password"
              required
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
            <TextField
              label="New password"
              type="password"
              autoComplete="new-password"
              required
              hint="At least 10 characters"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
            {passwordError && (
              <p role="alert" className="text-caption text-destructive">
                {passwordError}
              </p>
            )}
            <Button type="submit" loading={changingPassword} className="self-start">
              Update password
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
