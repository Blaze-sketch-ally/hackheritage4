import { cn } from "@/lib/utils";

const GRADIENT_ID = "skillbridge-mark-gradient";

/** The standalone "S" mark: a bridge-inspired stroke on a blue → cyan →
 * green gradient, sized in `em` so it scales with the font-size the caller
 * sets (sidebars/headers use ~28-32px; compact contexts can go smaller).
 * Pure inline SVG — no external asset, no CDN. */
export function SkillBridgeMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      className={cn("size-[1em] shrink-0", className)}
      role="img"
      aria-label="SkillBridge"
    >
      <defs>
        <linearGradient id={GRADIENT_ID} x1="2" y1="30" x2="30" y2="2" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="oklch(0.55 0.2 260)" />
          <stop offset="55%" stopColor="oklch(0.7 0.15 210)" />
          <stop offset="100%" stopColor="oklch(0.72 0.17 155)" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="9" fill={`url(#${GRADIENT_ID})`} />
      <path
        d="M20.5 9.5c-1-1-2.4-1.6-4-1.6-2.9 0-5.1 1.7-5.1 4 0 2.1 1.7 3.1 4.3 3.7l1.4.3c2.9.7 5.4 1.8 5.4 4.9 0 3.2-2.8 5.3-6.3 5.3-2.2 0-4.2-.8-5.6-2.2"
        fill="none"
        stroke="white"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/** Full lockup: mark + "SkillBridge" wordmark, "Skill" in the ambient
 * foreground color (dark in light mode, light in dark mode — via the
 * `text-foreground` token, no separate dark: override needed) and
 * "Bridge" in the same blue → cyan → green gradient as the mark. Sized via
 * `textClassName`/the surrounding font-size; defaults suit a ~14px sidebar
 * header row. Pass `markOnly` in very tight spaces (e.g. a collapsed rail)
 * to render just the icon. */
export function SkillBridgeLogo({
  className,
  markClassName,
  textClassName,
  markOnly = false,
}: {
  className?: string;
  markClassName?: string;
  textClassName?: string;
  markOnly?: boolean;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <SkillBridgeMark className={cn("text-[1.9rem]", markClassName)} />
      {markOnly ? (
        <span className="sr-only">SkillBridge</span>
      ) : (
        <span className={cn("text-lg font-bold tracking-tight", textClassName)}>
          <span className="text-foreground">Skill</span>
          <span className="bg-linear-to-r from-brand-blue via-brand-cyan to-brand-green bg-clip-text text-transparent">
            Bridge
          </span>
        </span>
      )}
    </span>
  );
}
