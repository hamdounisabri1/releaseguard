import { notFound } from "next/navigation";

// Any URL that no other route matches lands here, so its 404 renders inside the app
// shell (app/(app)/not-found.tsx) instead of the bare root layout. Explicit routes such
// as /dashboard always win over this catch-all.
export default function CatchAllPage(): never {
  notFound();
}
