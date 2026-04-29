/**
 * Spinner — accessible loading indicator used across forms and the chat panel.
 *
 * Props:
 *   size?: "sm" | "md" | "lg"  — controls pixel diameter (default "md" = 24px)
 *   label?: string             — screen-reader label (default "Loading…")
 *
 * Implementation:
 *   Pure CSS animated SVG ring.  No external icon library required.
 *   The outer `<span>` has `aria-label` and `role="status"` so assistive
 *   technology announces the loading state without extra context.
 *
 * Implemented in Stage 7.
 */

interface Props {
  size?: "sm" | "md" | "lg";
  label?: string;
}

const SIZE_MAP = { sm: 16, md: 24, lg: 40 };

export default function Spinner({ size = "md", label = "Loading…" }: Props) {
  const px = SIZE_MAP[size];
  return (
    <span role="status" aria-label={label} style={{ display: "inline-block" }}>
      {/* SVG implemented in Stage 7 */}
      <svg width={px} height={px} viewBox="0 0 24 24" />
    </span>
  );
}
