"use client";

import * as RadixTabs from "@radix-ui/react-tabs";
import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface TabItem {
  value: string;
  label: string;
  content: ReactNode;
}

export interface TabsProps {
  items: TabItem[];
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
}

export function Tabs({ items, defaultValue, value, onValueChange }: TabsProps) {
  return (
    <RadixTabs.Root
      defaultValue={defaultValue ?? items[0]?.value}
      value={value}
      onValueChange={onValueChange}
    >
      <RadixTabs.List className="flex gap-1 border-b border-border" aria-label="Tabs">
        {items.map((item) => (
          <RadixTabs.Trigger
            key={item.value}
            value={item.value}
            className={cn(
              "px-3 py-2 text-body font-medium text-muted-foreground",
              "border-b-2 border-transparent -mb-px",
              "data-[state=active]:border-primary data-[state=active]:text-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded-t-sm",
            )}
          >
            {item.label}
          </RadixTabs.Trigger>
        ))}
      </RadixTabs.List>
      {items.map((item) => (
        <RadixTabs.Content key={item.value} value={item.value} className="pt-4">
          {item.content}
        </RadixTabs.Content>
      ))}
    </RadixTabs.Root>
  );
}
