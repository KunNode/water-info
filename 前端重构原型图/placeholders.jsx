// Reusable sketchy SVG placeholders

function MapPlaceholder({ variant = 1 }) {
  // simple blob-style map outline + station dots
  return (
    <svg viewBox="0 0 800 460" preserveAspectRatio="xMidYMid meet">
      <defs>
        <pattern id="hatch" patternUnits="userSpaceOnUse" width="8" height="8" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="8" stroke="var(--hatch)" strokeWidth="1" />
        </pattern>
      </defs>
      {/* river / basin outline */}
      <path
        d="M40,120 Q120,60 220,90 T400,70 Q520,60 600,120 T760,180 Q740,260 660,290 T500,360 Q380,410 260,380 T80,340 Q30,260 40,120 Z"
        fill="url(#hatch)" stroke="var(--line)" strokeWidth="1.5"
      />
      {/* river line */}
      <path
        d="M60,200 Q200,180 320,230 T560,260 Q680,270 760,220"
        stroke="var(--blue)" strokeWidth="3" fill="none" opacity="0.75"
      />
      <path
        d="M320,230 Q360,300 420,320 Q470,335 520,380"
        stroke="var(--blue)" strokeWidth="2" fill="none" opacity="0.6"
      />
      {/* station dots */}
      {[
        [130,180,'S01','ok'],[240,150,'S02','ok'],[330,230,'S03','warn'],
        [420,200,'S04','ok'],[520,280,'S05','alert'],[600,210,'S06','ok'],
        [700,240,'S07','ok'],[250,300,'S08','warn'],[420,340,'S09','ok'],
        [560,360,'S10','alert'],[180,260,'S11','ok'],[660,150,'S12','ok'],
      ].map(([x,y,name,st],i) => (
        <g key={i}>
          <circle cx={x} cy={y} r={st==='alert'?10:7}
            fill={st==='alert'?'#d88a8a':st==='warn'?'#f5d76e':'var(--paper-card)'}
            stroke="var(--line)" strokeWidth="1.5" />
          {st==='alert' && <circle cx={x} cy={y} r="16" fill="none" stroke="#d88a8a" strokeWidth="1" opacity="0.6" />}
          <text x={x+12} y={y+4} fontFamily="var(--font-mono)" fontSize="10" fill="var(--ink-soft)">{name}</text>
        </g>
      ))}
      {/* legend */}
      <g transform="translate(30,420)" fontFamily="var(--font-mono)" fontSize="10" fill="var(--ink-soft)">
        <circle cx="6" cy="0" r="5" fill="var(--paper-card)" stroke="var(--line)" /><text x="18" y="3">正常</text>
        <circle cx="72" cy="0" r="5" fill="#f5d76e" stroke="var(--line)" /><text x="84" y="3">警戒</text>
        <circle cx="138" cy="0" r="6" fill="#d88a8a" stroke="var(--line)" /><text x="150" y="3">告警</text>
        <text x="210" y="3">— 河道 / 水系</text>
      </g>
    </svg>
  );
}

function SparkLine({ width = 220, height = 48, seed = 1, color = 'var(--blue)' }) {
  // deterministic pseudo-random
  const rand = (i) => {
    const x = Math.sin((seed + i) * 9.13) * 10000;
    return x - Math.floor(x);
  };
  const N = 28;
  const pts = Array.from({length: N}, (_,i) => {
    const x = (i / (N - 1)) * width;
    const y = height - (0.25 + rand(i) * 0.7) * height;
    return [x, y];
  });
  const d = pts.map((p, i) => (i===0?'M':'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  const area = d + ` L ${width},${height} L 0,${height} Z`;
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <path d={area} fill={color} opacity="0.12" />
      <path d={d} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

function BarChartPH({ width = 320, height = 120, seed = 3, bars = 14, color = 'var(--blue)' }) {
  const rand = (i) => {
    const x = Math.sin((seed + i) * 5.71) * 10000;
    return x - Math.floor(x);
  };
  const bw = width / (bars * 1.5);
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <line x1="0" y1={height-1} x2={width} y2={height-1} stroke="var(--line-soft)" />
      {Array.from({length: bars}).map((_, i) => {
        const h = (0.2 + rand(i) * 0.75) * (height - 8);
        const x = i * (bw * 1.5) + bw * 0.25;
        const y = height - h;
        return <rect key={i} x={x} y={y} width={bw} height={h} fill={color} opacity={0.75} />;
      })}
    </svg>
  );
}

function LineChartPH({ width = 600, height = 180, seeds = [1, 2], colors = ['var(--blue)', 'var(--ink-soft)'] }) {
  const rand = (s, i) => {
    const x = Math.sin((s + i) * 7.37) * 10000;
    return x - Math.floor(x);
  };
  const N = 40;
  const build = (s) => {
    const pts = Array.from({length: N}, (_,i) => {
      const x = (i / (N - 1)) * width;
      const y = 20 + (0.2 + rand(s, i) * 0.7) * (height - 40);
      return [x, y];
    });
    return pts.map((p, i) => (i===0?'M':'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ');
  };
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {[0.25, 0.5, 0.75].map(f => (
        <line key={f} x1="0" y1={height*f} x2={width} y2={height*f}
          stroke="var(--line-soft)" strokeDasharray="2 4" />
      ))}
      {seeds.map((s, i) => (
        <path key={i} d={build(s)} fill="none" stroke={colors[i] || 'var(--ink-soft)'} strokeWidth="1.5" />
      ))}
    </svg>
  );
}

function GaugePH({ value = 62, label = 'RISK' }) {
  const R = 54, cx = 70, cy = 70;
  const a0 = Math.PI, a1 = 0;
  const angle = a0 + (value / 100) * (a1 - a0);
  const p = (a) => [cx + Math.cos(a) * R, cy + Math.sin(a) * R];
  const [sx, sy] = p(a0), [ex, ey] = p(angle), [fx, fy] = p(a1);
  return (
    <svg width="140" height="90" viewBox="0 0 140 90">
      <path d={`M${sx},${sy} A${R},${R} 0 0 1 ${fx},${fy}`}
        fill="none" stroke="var(--line-soft)" strokeWidth="10" />
      <path d={`M${sx},${sy} A${R},${R} 0 0 1 ${ex},${ey}`}
        fill="none" stroke="var(--blue)" strokeWidth="10" />
      <text x={cx} y={cy - 4} textAnchor="middle" fontSize="22" fontWeight="600" fill="var(--ink)">{value}</text>
      <text x={cx} y={cy + 14} textAnchor="middle" fontSize="10" fill="var(--ink-mute)" fontFamily="var(--font-mono)">{label}</text>
    </svg>
  );
}

Object.assign(window, { MapPlaceholder, SparkLine, BarChartPH, LineChartPH, GaugePH });
