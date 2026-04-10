import React from 'react';

interface SparklineProps {
  data: number[];       // array of values (last 7 days)
  color: string;        // CSS color string e.g. '#3b82f6'
  width?: number;
  height?: number;
}

/** Mini sparkline / area chart for stats cards */
export const Sparkline: React.FC<SparklineProps> = ({
  data,
  color,
  width = 64,
  height = 28,
}) => {
  if (data.length < 2) return null;

  const max = Math.max(...data, 1);
  const min = 0;
  const range = max - min || 1;

  const W = width;
  const H = height;
  const PAD = 2;

  // Build polyline points
  const points = data.map((v, i) => {
    const x = PAD + (i / (data.length - 1)) * (W - PAD * 2);
    const y = H - PAD - ((v - min) / range) * (H - PAD * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  // Area fill polygon (close the shape)
  const first = points[0];
  const last = points[points.length - 1];
  const areaPoints = `${PAD},${H} ${first} ${last} ${W - PAD},${H}`;

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden="true">
      <defs>
        <linearGradient id={`sg-${color.replace('#', '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {/* Area fill */}
      <polygon
        points={areaPoints}
        fill={`url(#sg-${color.replace('#', '')})`}
      />
      {/* Line */}
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Last value dot */}
      <circle
        cx={Number.parseFloat(last.split(',')[0])}
        cy={Number.parseFloat(last.split(',')[1])}
        r="2"
        fill={color}
      />
    </svg>
  );
};
