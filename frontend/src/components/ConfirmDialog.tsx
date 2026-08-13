"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import { Dialog } from "@/components/Dialog";

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  /** Called when the user confirms; may be async (e.g. an archive/delete API call). */
  onConfirm: () => void | Promise<void>;
  destructive?: boolean;
}

/** Confirmation gate for destructive actions (FR-029: archive/delete require
 * explicit confirmation given the irreversible nature of delete). */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  onConfirm,
  destructive = true,
}: ConfirmDialogProps) {
  const [submitting, setSubmitting] = useState(false);

  async function handleConfirm() {
    setSubmitting(true);
    try {
      await onConfirm();
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button
            variant={destructive ? "destructive" : "primary"}
            onClick={handleConfirm}
            loading={submitting}
          >
            {confirmLabel}
          </Button>
        </>
      }
    />
  );
}
