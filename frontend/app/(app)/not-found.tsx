import Link from "next/link";
import { FileQuestion } from "lucide-react";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <section className="flex flex-1 flex-col items-center justify-center gap-3 py-16 text-center">
      <FileQuestion className="size-10 text-muted-foreground" aria-hidden="true" />
      <h1 className="text-xl font-semibold tracking-tight">Page not found</h1>
      <p className="max-w-sm text-sm text-muted-foreground">
        This page doesn&apos;t exist, or it hasn&apos;t been built yet.
      </p>
      <Button asChild variant="outline">
        <Link href="/dashboard">Back to dashboard</Link>
      </Button>
    </section>
  );
}
