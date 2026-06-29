"use client";

import * as React from "react";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

export interface StepperStep {
  label: string;
  description?: string;
}

interface StepperProps {
  steps: StepperStep[];
  /** 0-based index of the current step. */
  currentStep: number;
  className?: string;
}

/** Horizontal progress stepper — Step 1 -> Step 2 -> Step 3... */
function Stepper({ steps, currentStep, className }: StepperProps) {
  return (
    <ol className={cn("flex w-full items-start", className)}>
      {steps.map((step, index) => {
        const isComplete = index < currentStep;
        const isCurrent = index === currentStep;
        const isLast = index === steps.length - 1;

        return (
          <li key={step.label} className={cn("flex items-center", !isLast && "flex-1")}>
            <div className="flex flex-col items-center text-center">
              <div
                className={cn(
                  "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors",
                  isComplete && "bg-primary text-primary-foreground",
                  isCurrent && "border-2 border-primary text-primary",
                  !isComplete && !isCurrent && "border border-border text-muted-foreground"
                )}
              >
                {isComplete ? <Check size={14} /> : index + 1}
              </div>
              <span
                className={cn(
                  "mt-1.5 max-w-24 text-xs font-medium",
                  isCurrent ? "text-foreground" : "text-muted-foreground"
                )}
              >
                {step.label}
              </span>
              {step.description && (
                <span className="max-w-28 text-[10px] text-muted-foreground">{step.description}</span>
              )}
            </div>
            {!isLast && (
              <div
                className={cn(
                  "mx-2 mt-3.5 h-0.5 flex-1 rounded transition-colors",
                  isComplete ? "bg-primary" : "bg-border"
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

export { Stepper };
