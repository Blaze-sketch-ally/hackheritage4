import Image from "next/image";
import { cn } from "@/lib/utils";

// The source PNG's real pixel dimensions -- passed to next/image as the
// intrinsic size; display size is controlled by the `height` prop below
// via inline style (width follows automatically), so this never has to
// match the rendered size.
const WORDMARK_SRC = "/branding/skillbridge-wordmark.png";
const WORDMARK_INTRINSIC_WIDTH = 2172;
const WORDMARK_INTRINSIC_HEIGHT = 724;

/**
 * The standalone "SkillBridge" wordmark (public/branding/skillbridge-
 * wordmark.png) -- "Skill" in dark navy, "Bridge" in the blue -> cyan ->
 * teal gradient, exactly as designed. This is the ONLY place that image
 * is rendered from; never recreate the treatment with HTML text/CSS
 * gradients, and never render it without `SkillBridgeEmblem` unless the
 * emblem genuinely doesn't fit (see SkillBridgeBrand's `showWordmark`).
 *
 * Sized by height only -- width is derived from the source's own aspect
 * ratio (2172:724), so it can never be stretched or squashed.
 *
 * Like the emblem, the source PNG has no alpha channel (flat near-white
 * background) -- the same optional white chip wrapper applies here, for
 * the same reason (see skillbridge-emblem.tsx's docstring).
 */
export function SkillBridgeWordmark({
  height = 20,
  className,
  chip = true,
  chipClassName,
  priority,
  alt = "SkillBridge",
}: {
  /** Rendered height in px; width follows the source's aspect ratio. */
  height?: number;
  className?: string;
  /** Wrap in the white chip. Set to false only when a caller (e.g.
   * SkillBridgeBrand) already provides its own shared chip around this +
   * the emblem -- never to expose the raw near-white background on a
   * dark surface unwrapped. */
  chip?: boolean;
  chipClassName?: string;
  priority?: boolean;
  /** Set to "" when this wordmark sits beside a SkillBridgeEmblem inside
   * an already-labelled brand link (see SkillBridgeBrand). Defaults to a
   * real name for standalone use. */
  alt?: string;
}) {
  const renderedWidth = Math.round(height * (WORDMARK_INTRINSIC_WIDTH / WORDMARK_INTRINSIC_HEIGHT));

  const img = (
    <Image
      src={WORDMARK_SRC}
      alt={alt}
      width={WORDMARK_INTRINSIC_WIDTH}
      height={WORDMARK_INTRINSIC_HEIGHT}
      priority={priority}
      // Without `sizes`, next/image requests its largest configured
      // breakpoint for an ~800KB source that only ever renders this
      // small -- pinning `sizes` to the actual rendered width gets a
      // small, fast, correctly-cached variant instead.
      sizes={`${renderedWidth}px`}
      style={{ height, width: "auto" }}
      className={cn("object-contain", className)}
    />
  );

  if (!chip) return img;

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-md bg-white px-1.5 py-0.5",
        chipClassName,
      )}
    >
      {img}
    </span>
  );
}
