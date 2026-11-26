import { LoadingState } from "@/components/states/loading-state";

/** Shown inside the app shell while a page's data streams in. */
export default function AppLoading() {
  return <LoadingState label="Loading page…" />;
}
