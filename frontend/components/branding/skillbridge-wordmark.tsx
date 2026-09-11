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
 * emblem genuinely doesn't fit (see SkillBridgeBrand's `emblem={false}`).
 *
 * Sized by height only -- width is derived from the source's own aspect
 * ratio (2172:724), so it can never be stretched or squashed.
 */
export function SkillBridgeWordmark({
  height = 20,
  className,
  priority,
  alt = "SkillBridge",
}: {
  /** Rendered height in px; width follows the source's aspect ratio. */
  height?: number;
  className?: string;
  priority?: boolean;
  /** Set to "" when this wordmark sits beside a SkillBridgeEmblem inside
   * an already-labelled brand link (see SkillBridgeBrand). Defaults to a
   * real name for standalone use. */
  alt?: string;
}) {
  return (
    <Image
      src={WORDMARK_SRC}
      alt={alt}
      width={WORDMARK_INTRINSIC_WIDTH}
      height={WORDMARK_INTRINSIC_HEIGHT}
      priority={priority}
      style={{ height, width: "auto" }}
      className={cn("object-contain", className)}
    />
  );
}
