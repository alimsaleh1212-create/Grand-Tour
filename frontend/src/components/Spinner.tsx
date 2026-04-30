interface Props {
  size?: "sm" | "md" | "lg";
  label?: string;
  color?: string;
}

const SIZE_MAP = { sm: 16, md: 24, lg: 40 };

export default function Spinner({ size = "md", label = "Loading…", color = "currentColor" }: Props) {
  const px = SIZE_MAP[size];
  return (
    <span
      role="status"
      aria-label={label}
      style={{ display: "inline-flex", alignItems: "center" }}
    >
      <svg
        width={px}
        height={px}
        viewBox="0 0 24 24"
        fill="none"
        style={{ animation: "spin 0.8s linear infinite" }}
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" stroke={color} strokeWidth="2.5" strokeOpacity="0.2" />
        <path
          d="M12 2 A10 10 0 0 1 22 12"
          stroke={color}
          strokeWidth="2.5"
          strokeLinecap="round"
        />
      </svg>
    </span>
  );
}
