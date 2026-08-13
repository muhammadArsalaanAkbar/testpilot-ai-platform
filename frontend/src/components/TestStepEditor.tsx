"use client";

import { GripVertical, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/Button";
import { Card, CardContent } from "@/components/Card";
import { Select } from "@/components/form/Select";
import { TextField } from "@/components/form/TextField";

export type TestStepActionType =
  | "navigate"
  | "click"
  | "type"
  | "submit"
  | "assert_url"
  | "assert_content"
  | "assert_element";

export interface TestStepDraft {
  action_type: TestStepActionType;
  target_descriptor: string;
  input_value: string;
  expected_assertion: string;
}

interface ActionConfig {
  label: string;
  fields: Array<"target" | "input" | "assertion">;
  targetLabel?: string;
  inputLabel?: string;
  assertionLabel?: string;
}

const ACTION_CONFIG: Record<TestStepActionType, ActionConfig> = {
  navigate: { label: "Navigate", fields: ["target"], targetLabel: "URL or path" },
  click: { label: "Click", fields: ["target"], targetLabel: "Element (selector or description)" },
  type: {
    label: "Type text",
    fields: ["target", "input"],
    targetLabel: "Element (selector or description)",
    inputLabel: "Text to type",
  },
  submit: { label: "Submit form", fields: ["target"], targetLabel: "Form (selector or description)" },
  assert_url: { label: "Assert URL", fields: ["assertion"], assertionLabel: "Expected URL or path" },
  assert_content: { label: "Assert page content", fields: ["assertion"], assertionLabel: "Expected text" },
  assert_element: {
    label: "Assert element state",
    fields: ["target", "assertion"],
    targetLabel: "Element (selector or description)",
    assertionLabel: "Expected state",
  },
};

const ACTION_OPTIONS = Object.entries(ACTION_CONFIG).map(([value, config]) => ({
  value,
  label: config.label,
}));

function emptyStep(): TestStepDraft {
  return { action_type: "navigate", target_descriptor: "", input_value: "", expected_assertion: "" };
}

export interface TestStepEditorProps {
  value: TestStepDraft[];
  onChange: (steps: TestStepDraft[]) => void;
}

/** Structured step builder for a test case's ordered actions (FR-053) —
 * fields shown per step depend on its action type, so the form only asks
 * for what that action actually needs. */
export function TestStepEditor({ value, onChange }: TestStepEditorProps) {
  function updateStep(index: number, patch: Partial<TestStepDraft>) {
    onChange(value.map((step, i) => (i === index ? { ...step, ...patch } : step)));
  }

  function addStep() {
    onChange([...value, emptyStep()]);
  }

  function removeStep(index: number) {
    onChange(value.filter((_, i) => i !== index));
  }

  function moveStep(index: number, direction: -1 | 1) {
    const target = index + direction;
    if (target < 0 || target >= value.length) return;
    const current = value[index];
    const swapped = value[target];
    if (!current || !swapped) return;
    const next = [...value];
    next[index] = swapped;
    next[target] = current;
    onChange(next);
  }

  return (
    <div className="flex flex-col gap-3">
      {value.map((step, index) => {
        const config = ACTION_CONFIG[step.action_type];
        return (
          <Card key={index}>
            <CardContent className="flex flex-col gap-3 pt-4">
              <div className="flex items-start gap-3">
                <div className="flex flex-col items-center gap-1 pt-6 text-muted-foreground">
                  <GripVertical className="h-4 w-4" aria-hidden="true" />
                  <span className="text-caption">{index + 1}</span>
                </div>
                <div className="flex flex-1 flex-col gap-3">
                  <Select
                    label="Action"
                    options={ACTION_OPTIONS}
                    value={step.action_type}
                    onChange={(e) => updateStep(index, { action_type: e.target.value as TestStepActionType })}
                  />
                  {config.fields.includes("target") && (
                    <TextField
                      label={config.targetLabel ?? "Target"}
                      value={step.target_descriptor}
                      onChange={(e) => updateStep(index, { target_descriptor: e.target.value })}
                    />
                  )}
                  {config.fields.includes("input") && (
                    <TextField
                      label={config.inputLabel ?? "Input"}
                      value={step.input_value}
                      onChange={(e) => updateStep(index, { input_value: e.target.value })}
                    />
                  )}
                  {config.fields.includes("assertion") && (
                    <TextField
                      label={config.assertionLabel ?? "Expected result"}
                      value={step.expected_assertion}
                      onChange={(e) => updateStep(index, { expected_assertion: e.target.value })}
                    />
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={index === 0}
                    onClick={() => moveStep(index, -1)}
                    aria-label={`Move step ${index + 1} up`}
                  >
                    ↑
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={index === value.length - 1}
                    onClick={() => moveStep(index, 1)}
                    aria-label={`Move step ${index + 1} down`}
                  >
                    ↓
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => removeStep(index)}
                    aria-label={`Remove step ${index + 1}`}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        );
      })}
      <Button type="button" variant="outline" onClick={addStep} className="self-start">
        <Plus className="h-4 w-4" aria-hidden="true" />
        Add step
      </Button>
    </div>
  );
}
