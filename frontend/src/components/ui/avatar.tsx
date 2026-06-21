import * as React from "react";
import { cn } from "@/lib/utils";

interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  src?: string;
  fallback: string;
}

export function Avatar({ className, src, fallback, ...props }: AvatarProps) {
  return (
    <div
      className={cn(
        "relative flex h-8 w-8 shrink-0 overflow-hidden rounded-lg border border-border bg-secondary text-foreground items-center justify-center font-medium text-xs select-none uppercase",
        className
      )}
      {...props}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt="Avatar" className="h-full w-full object-cover" />
      ) : (
        <span className="text-primary font-bold">{fallback}</span>
      )}
    </div>
  );
}
