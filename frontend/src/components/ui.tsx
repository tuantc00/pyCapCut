import * as TooltipPrimitive from "@radix-ui/react-tooltip";
import { X } from "lucide-react";
import {
  forwardRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes
} from "react";
import { useStudio } from "../store";

export function Tooltip({
  vi,
  en,
  children
}: {
  vi: string;
  en: string;
  children: ReactNode;
}) {
  const language = useStudio((state) => state.language);
  return (
    <TooltipPrimitive.Root delayDuration={450}>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content className="tooltip" sideOffset={8}>
          {language === "vi" ? vi : en}
          <TooltipPrimitive.Arrow className="tooltip-arrow" />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  tooltip: { vi: string; en: string };
  variant?: "default" | "primary" | "danger" | "ghost";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ tooltip, variant = "default", className = "", ...props }, ref) => (
    <Tooltip vi={tooltip.vi} en={tooltip.en}>
      <button ref={ref} className={`button button-${variant} ${className}`} {...props} />
    </Tooltip>
  )
);
Button.displayName = "Button";

export function Field({
  label,
  hint,
  children
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>
        {label}
        {hint && <small>{hint}</small>}
      </span>
      {children}
    </label>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className = "", ...props }, ref) => (
    <input ref={ref} className={`input ${className}`} {...props} />
  )
);
Input.displayName = "Input";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className = "", ...props }, ref) => (
    <select ref={ref} className={`input ${className}`} {...props} />
  )
);
Select.displayName = "Select";

export function Panel({
  title,
  actions,
  className = "",
  children
}: {
  title?: string;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <header className="panel-header">
          <h2>{title}</h2>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function Notice() {
  const notice = useStudio((state) => state.notice);
  const setNotice = useStudio((state) => state.setNotice);
  if (!notice) return null;
  return (
    <div className={`notice notice-${notice.kind}`}>
      <span>{notice.text}</span>
      <button onClick={() => setNotice(null)} aria-label="Close">
        <X size={15} />
      </button>
    </div>
  );
}
