import { useState } from "react";
import clsx from "clsx";

interface CardProps {
  title: string;
  className?: string;
  children: React.ReactNode;
  onTimeRange?: (range: string) => void;
  onExport?: () => void;
  onRawView?: () => void;
}

export default function Card({
  title,
  className,
  children,
  onTimeRange,
  onExport,
  onRawView,
}: CardProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className={clsx("card", className)}>
      <div className="card-header">
        <span className="card-title">{title}</span>
        <button
          className="card-menu-btn"
          onClick={() => setMenuOpen((v) => !v)}
          title="Card options"
        >
          &#8942;
        </button>
        {menuOpen && (
          <div className="card-menu-dropdown">
            {onTimeRange && (
              <>
                <button onClick={() => { onTimeRange("1h"); setMenuOpen(false); }}>Last 1h</button>
                <button onClick={() => { onTimeRange("6h"); setMenuOpen(false); }}>Last 6h</button>
                <button onClick={() => { onTimeRange("24h"); setMenuOpen(false); }}>Last 24h</button>
              </>
            )}
            {onExport && (
              <button onClick={() => { onExport(); setMenuOpen(false); }}>Export</button>
            )}
            {onRawView && (
              <button onClick={() => { onRawView(); setMenuOpen(false); }}>Raw View</button>
            )}
          </div>
        )}
      </div>
      <div className="card-body">{children}</div>
    </div>
  );
}
