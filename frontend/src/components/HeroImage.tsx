import { useState } from "react";

interface HeroImageProps {
  src: string;
  alt: string;
  className?: string;
}

export function HeroImage({ src, alt, className }: HeroImageProps) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <span className={`hero-image-fallback ${className ?? ""}`} aria-label={alt}>
        {alt.slice(0, 1).toUpperCase()}
      </span>
    );
  }

  return (
    <img
      className={className}
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}
