"use client";

import { useQuery } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { useState } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { LOGIN_PATH } from "@/lib/auth-routes";
import { ApiError } from "@/services/api";
import { logout, meQueryOptions, roleLabel } from "@/services/auth";

/** Up to two initials from a display name ("Ada Lovelace" → "AL"). */
export function initials(name: string): string {
  const letters = name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() ?? "");
  return (letters.length > 1 ? letters[0] + letters.at(-1) : (letters[0] ?? "")) || "?";
}

/**
 * Signs out, then loads the login page in full: a full load drops every cached query of the old
 * session. A 401 means the session is already gone, which counts as signed out. Any other failure
 * (network, 5xx, a refused Origin) leaves the session alive, so the user stays and is told.
 */
export async function signOut(): Promise<boolean> {
  try {
    await logout();
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 401)) return false;
  }
  window.location.replace(LOGIN_PATH);
  return true;
}

/** The signed-in user (from the shared `/auth/me` query) and the sign-out action. */
export function AccountMenu() {
  const { data: me } = useQuery(meQueryOptions);
  const [signingOut, setSigningOut] = useState(false);
  const [signOutFailed, setSignOutFailed] = useState(false);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="size-9 rounded-full"
          aria-label="Account menu"
        >
          <Avatar className="size-8">
            <AvatarFallback>{me ? initials(me.user.display_name) : ""}</AvatarFallback>
          </Avatar>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        {me ? (
          <DropdownMenuLabel className="flex flex-col gap-0.5 font-normal">
            <span className="truncate text-sm font-medium text-foreground">
              {me.user.display_name}
            </span>
            <span className="truncate text-xs text-muted-foreground">{me.user.email}</span>
            <span className="truncate text-xs text-muted-foreground">
              {me.workspace.name} · {roleLabel(me.role)}
            </span>
          </DropdownMenuLabel>
        ) : (
          <DropdownMenuLabel>Account</DropdownMenuLabel>
        )}
        <DropdownMenuSeparator />
        <DropdownMenuItem
          disabled={signingOut}
          onSelect={(event) => {
            event.preventDefault(); // keep the menu open while the request runs
            setSigningOut(true);
            setSignOutFailed(false);
            void signOut().then((done) => {
              if (!done) {
                setSigningOut(false);
                setSignOutFailed(true);
              }
            });
          }}
        >
          <LogOut aria-hidden="true" />
          {signingOut ? "Signing out…" : "Sign out"}
        </DropdownMenuItem>
        {signOutFailed ? (
          <p role="alert" className="px-2 py-1.5 text-xs text-destructive">
            Couldn&apos;t sign out: you&apos;re still signed in. Try again in a moment.
          </p>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
