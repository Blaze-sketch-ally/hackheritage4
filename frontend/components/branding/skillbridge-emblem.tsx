import Image from "next/image";
import { cn } from "@/lib/utils";

// The source PNG's real pixel dimensions (1:1 square) -- passed to
// next/image as the intrinsic size; display size is controlled entirely
// by the `size` prop below via inline style, so this never has to match
// the rendered size.
const EMBLEM_SRC = "/branding/skillbridge-emblem.png";
const EMBLEM_INTRINSIC_SIZE = 1254;

/**
 * The standalone SkillBridge "S" emblem (public/branding/skillbridge-
 * emblem.png) -- the stylized mark only, never combined with the
 * wordmark or any other text/icon. Use this alone for compact spaces
 * (mobile branding, a loading/splash screen, a favicon-sized mark); use
 * `SkillBridgeBrand` when the full lockup (emblem + wordmark) is wanted.
 *
 * The source PNG has no alpha channel -- its background is a flat
 * near-white (~#fefefe), which blends into this app's light-theme
 * surfaces but would show as a stray light box on a dark surface. The
 * small white chip below is the ONLY concession to that: it turns the
 * flat background into a deliberate-looking badge instead of a
 * rendering artifact, without touching the asset itself. It is visually
 * inert in light mode (white-on-white).
 */
export function SkillBridgeEmblem({
  size = 28,
  className,
  chip = true,
  chipClassName,
  priority,
  alt = "SkillBridge",
}: {
  /** Rendered height AND width in px -- the source is a 1:1 square, so a
   * single number fully determines the size without ever distorting it. */
  size?: number;
  /** Applied to the <img> itself. */
  className?: string;
  /** Wrap in the white chip (see module docstring). Set to false only
   * when a caller (e.g. SkillBridgeBrand) already provides its own
   * shared chip around this + the wordmark -- never to expose the raw
   * near-white background on a dark surface unwrapped. */
  chip?: boolean;
  /** Applied to the white chip wrapper -- override only for spacing/
   * layout, never to recolor or hide the chip. */
  chipClassName?: string;
  priority?: boolean;
  /** Set to "" when this emblem sits beside a SkillBridgeWordmark inside
   * an already-labelled brand link (see SkillBridgeBrand) -- avoids a
   * duplicate screen-reader announcement. Defaults to a real name for
   * standalone use (splash/loading screens, compact mobile branding). */
  alt?: string;
}) {
  const img = (
    <Image
      src={EMBLEM_SRC}
      alt={alt}
      width={EMBLEM_INTRINSIC_SIZE}
      height={EMBLEM_INTRINSIC_SIZE}
      priority={priority}
      // Without `sizes`, next/image assumes this could render as wide as
      // the viewport and requests its largest configured breakpoint --
      // an expensive resize of an ~900KB source for a mark that only
      // ever renders at `size` px. Pinning `sizes` to the actual
      // rendered width gets a small, fast, correctly-cached variant.
      sizes={`${size}px`}
      style={{ height: size, width: size }}
      className={cn("rounded-[3px] object-contain", className)}
    />
  );

  if (!chip) return img;

  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-md bg-white p-0.5",
        chipClassName,
      )}
    >
      {img}
    </span>
  );
}
