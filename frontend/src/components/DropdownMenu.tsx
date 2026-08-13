"use client";

import * as RadixDropdown from "@radix-ui/react-dropdown-menu";
import { Check } from "lucide-react";
import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface DropdownMenuItemConfig {
  key: string;
  label: string;
  onSelect?: () => void;
  destructive?: boolean;
  disabled?: boolean;
  selected?: boolean;
}

export interface DropdownMenuProps {
  trigger: ReactNode;
  items: DropdownMenuItemConfig[];
  align?: "start" | "center" | "end";
}

export function DropdownMenu({ trigger, items, align = "end" }: DropdownMenuProps) {
  return (
    <RadixDropdown.Root>
      <RadixDropdown.Trigger asChild>{trigger}</RadixDropdown.Trigger>
      <RadixDropdown.Portal>
        <RadixDropdown.Content
          align={align}
          sideOffset={4}
          className={cn(
            "z-50 min-w-[10rem] rounded-md border border-border bg-card p-1 text-card-foreground shadow-md",
            "data-[state=open]:animate-in data-[state=open]:fade-in",
          )}
        >
          {items.map((item) => (
            <RadixDropdown.Item
              key={item.key}
              disabled={item.disabled}
              onSelect={item.onSelect}
              className={cn(
                "flex cursor-pointer items-center justify-between gap-2 rounded-sm px-2 py-1.5 text-body",
                "outline-none data-[highlighted]:bg-muted",
                "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
                item.destructive && "text-destructive",
              )}
            >
              {item.label}
              {item.selected && <Check className="h-4 w-4" aria-hidden="true" />}
            </RadixDropdown.Item>
          ))}
        </RadixDropdown.Content>
      </RadixDropdown.Portal>
    </RadixDropdown.Root>
  );
}
