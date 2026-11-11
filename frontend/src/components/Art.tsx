import { useEffect, useId, useState } from "react";
import { categoryOf } from "@/lib/categories";
import { contourPaths } from "@/lib/contour";
import { cn } from "@/lib/cn";

/** Generated terrain: unique per seed, tinted by category. Used as the backdrop and as the photo fallback. */
export function ContourArt({ seed, category = "heritage", className, lines = 9 }: { seed: string; category?: string; className?: string; lines?: number }) {
  const c = categoryOf(category);
  const paths = contourPaths(seed, lines);
  const gid = "g" + useId().replace(/[^a-zA-Z0-9]/g, "");
  return (
    <svg viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice" className={cn("size-full", className)} aria-hidden>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor={c.from} />
          <stop offset="1" stopColor={c.to} />
        </linearGradient>
      </defs>
      <rect width="400" height="300" fill={`url(#${gid})`} />
      {paths.map((d, i) => (
        <path key={i} d={d} fill="none" stroke={c.line} strokeOpacity={0.14 + (i % 3 === 0 ? 0.16 : 0)} strokeWidth={i % 3 === 0 ? 1.6 : 1} />
      ))}
    </svg>
  );
}

/** A photo that fades in over the generated terrain. If it fails to load, the terrain simply stays. */
export function PlaceImage({ src, name, category, className, iconSize = 28 }: { src?: string | null; name: string; category: string; className?: string; iconSize?: number }) {
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setReady(false);
    setFailed(false);
  }, [src]);
  const Icon = categoryOf(category).icon;
  const showPhoto = !!src && !failed;
  return (
    <div className={cn("relative overflow-hidden bg-mist-100", className)}>
      <ContourArt seed={name} category={category} />
      {!showPhoto && (
        <div className="absolute inset-0 grid place-items-center text-ink-900/35">
          <Icon size={iconSize} strokeWidth={1.5} />
        </div>
      )}
      {showPhoto && (
        <img
          src={src!}
          alt={name}
          loading="lazy"
          decoding="async"
          referrerPolicy="no-referrer"
          onLoad={() => setReady(true)}
          onError={() => setFailed(true)}
          className={cn("absolute inset-0 size-full object-cover transition-opacity duration-500", ready ? "opacity-100" : "opacity-0")}
        />
      )}
    </div>
  );
}
