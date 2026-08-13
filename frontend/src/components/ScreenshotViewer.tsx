"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";

export interface Screenshot {
  id: string;
  url: string;
  capturedAt: string;
}

export interface ScreenshotViewerProps {
  screenshots: Screenshot[];
}

/** Thumbnail grid + full-screen lightbox for a result's captured
 * screenshots (T154, FR-072). Built directly on Radix Dialog primitives
 * (not the generic text-sized `Dialog` component) since a lightbox needs
 * near-full-viewport sizing — focus trap/Escape-to-close/return-focus still
 * come from Radix, same accessibility guarantees as the rest of the design
 * system's overlays. */
export function ScreenshotViewer({ screenshots }: ScreenshotViewerProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  if (screenshots.length === 0) {
    return null;
  }

  const current = openIndex !== null ? screenshots[openIndex] : null;

  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
        {screenshots.map((shot, index) => (
          <button
            key={shot.id}
            type="button"
            onClick={() => setOpenIndex(index)}
            className="group overflow-hidden rounded-md border border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- signed, short-lived URLs; not a candidate for build-time optimization */}
            <img
              src={shot.url}
              alt={`Screenshot captured ${new Date(shot.capturedAt).toLocaleString()}`}
              className="aspect-video w-full object-cover object-top transition-transform group-hover:scale-105"
            />
          </button>
        ))}
      </div>

      <RadixDialog.Root open={current !== null} onOpenChange={(open) => !open && setOpenIndex(null)}>
        <RadixDialog.Portal>
          <RadixDialog.Overlay className="fixed inset-0 z-50 bg-black/80" />
          <RadixDialog.Content
            className="fixed inset-4 z-50 flex flex-col items-center justify-center gap-3 focus:outline-none sm:inset-10"
            aria-describedby={undefined}
          >
            <RadixDialog.Title className="sr-only">
              Screenshot {openIndex !== null ? openIndex + 1 : ""} of {screenshots.length}
            </RadixDialog.Title>
            <RadixDialog.Close
              aria-label="Close screenshot viewer"
              className="absolute right-2 top-2 rounded-md bg-black/50 p-2 text-white hover:bg-black/70"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </RadixDialog.Close>

            {current && (
              // eslint-disable-next-line @next/next/no-img-element -- see thumbnail note above
              <img
                src={current.url}
                alt={`Screenshot captured ${new Date(current.capturedAt).toLocaleString()}`}
                className="max-h-full max-w-full rounded-md object-contain"
              />
            )}

            {screenshots.length > 1 && openIndex !== null && (
              <div className="flex items-center gap-4">
                <button
                  type="button"
                  onClick={() => setOpenIndex((i) => (i !== null ? (i - 1 + screenshots.length) % screenshots.length : i))}
                  aria-label="Previous screenshot"
                  className="rounded-md bg-black/50 p-2 text-white hover:bg-black/70"
                >
                  <ChevronLeft className="h-5 w-5" aria-hidden="true" />
                </button>
                <span className="text-caption text-white">
                  {openIndex + 1} / {screenshots.length}
                </span>
                <button
                  type="button"
                  onClick={() => setOpenIndex((i) => (i !== null ? (i + 1) % screenshots.length : i))}
                  aria-label="Next screenshot"
                  className={cn("rounded-md bg-black/50 p-2 text-white hover:bg-black/70")}
                >
                  <ChevronRight className="h-5 w-5" aria-hidden="true" />
                </button>
              </div>
            )}
          </RadixDialog.Content>
        </RadixDialog.Portal>
      </RadixDialog.Root>
    </>
  );
}
