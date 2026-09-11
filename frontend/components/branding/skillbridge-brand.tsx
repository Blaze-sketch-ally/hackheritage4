import { cn } from "@/lib/utils";
import { SkillBridgeEmblem } from "@/components/branding/skillbridge-emblem";
import { SkillBridgeWordmark } from "@/components/branding/skillbridge-wordmark";

/** wordmark-height / emblem-size ratio that lines up the two marks' actual
 * ink (glyph) heights, not their raw canvas heights -- measured directly
 * from the source PNGs: the emblem's "S" glyph fills ~70% of its square
 * canvas, the wordmark's letters fill ~48% of its canvas height, so
 * `wordmarkHeight = emblemSize * (0.70 / 0.48)` puts both at the same
 * visual cap-height instead of matching arbitrary bounding boxes. */
const WORDMARK_TO_EMBLEM_RATIO = 0.7 / 0.48;

/**
 * The full SkillBridge lockup: the emblem and wordmark side by side, as
 * two separate images (never a single flattened asset). This component
 * only controls layout/spacing/sizing -- it renders no link and no
 * accessible name of its own, since every current use sits inside an
 * existing `<Link aria-label="SkillBridge home">` (see e.g.
 * components/auth/auth-shell.tsx); both images are therefore alt="" here
 * to avoid a duplicate screen-reader announcement of the same name.
 *
 * Both source PNGs have an opaque near-white background (no alpha
 * channel) -- rendered separately, each would show its own disjoint
 * white rectangle on a dark surface. This component wraps BOTH in one
 * shared white chip instead (each child's own individual chip disabled
 * via `chip={false}`), so the pair reads as a single deliberate badge,
 * never as two stray boxes with a gap between them. Invisible in light
 * mode (white-on-white).
 */
export function SkillBridgeBrand({
  emblemSize = 28,
  showWordmark = true,
  wordmarkClassName,
  gapClassName = "gap-1.5",
  chipClassName,
  className,
  priority,
}: {
  /** Emblem height/width in px; the wordmark's height is derived from it
   * (see WORDMARK_TO_EMBLEM_RATIO) so the pair never needs two sizes. */
  emblemSize?: number;
  /** Set to false where the wordmark genuinely doesn't fit at ANY size
   * (e.g. a very narrow mobile header) -- renders the emblem alone
   * rather than cramming or shrinking the wordmark unreadably. */
  showWordmark?: boolean;
  /** Tailwind visibility classes (e.g. "hidden lg:inline-block") for the
   * wordmark image itself, when it should drop out only BELOW a given
   * breakpoint rather than never render at all -- use this instead of a
   * JS media-query when the constraint is viewport width, so it's pure
   * CSS and can't cause a hydration mismatch. */
  wordmarkClassName?: string;
  gapClassName?: string;
  /** Applied to the shared white chip -- override only for spacing/
   * layout, never to recolor or hide it. */
  chipClassName?: string;
  className?: string;
  priority?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center rounded-lg bg-white px-1.5 py-1",
        gapClassName,
        chipClassName,
        className,
      )}
    >
      <SkillBridgeEmblem size={emblemSize} priority={priority} chip={false} alt="" />
      {showWordmark ? (
        <SkillBridgeWordmark
          height={Math.round(emblemSize * WORDMARK_TO_EMBLEM_RATIO)}
          priority={priority}
          chip={false}
          alt=""
          className={wordmarkClassName}
        />
      ) : null}
    </span>
  );
}
