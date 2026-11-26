import { Skeleton } from "@/components/ui/skeleton";

type LoadingStateProps = {
  /** Read by screen readers; the skeleton itself is hidden from them. */
  label?: string;
  /** Number of placeholder rows, roughly the size of the content that will replace them. */
  rows?: number;
};

/** Skeleton placeholder while data loads (no spinner: the layout shouldn't jump when it arrives). */
export function LoadingState({ label = "Loading…", rows = 3 }: LoadingStateProps) {
  return (
    <div role="status" aria-live="polite" aria-busy="true" className="flex flex-col gap-4">
      <span className="sr-only">{label}</span>
      <div aria-hidden="true" className="flex flex-col gap-4">
        <Skeleton className="h-8 w-48" />
        {Array.from({ length: rows }, (_, row) => (
          <Skeleton key={row} className="h-16 w-full" />
        ))}
      </div>
    </div>
  );
}
