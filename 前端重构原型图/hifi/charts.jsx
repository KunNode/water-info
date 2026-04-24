// Charts & visual placeholders (hi-fi, glow + gradient)

function rand(seed, i) {
  const x = Math.sin((seed + i) * 9.13) * 10000;
  return x - Math.floor(x);
}

function GlowLine({ width = 600, height = 180, seeds = [1], colors = ['var(--brand-2)'], glow = true, area = true, animate = false }) {
  const N = 50;
  const pad = 12;
  const gid = React.useId();
  const build = (s) => {
    const pts = Array.from({length: N}, (_,i) => {
      const x = pad + (i / (N - 1)) * (width - pad * 2);
      const y = pad + (0.15 + rand(s, i) * 0.7) * (height - pad * 2);
      return [x, y];
    });
    return { d: pts.map((p, i) => (i===0?'M':'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' '),
             areaD: pts.map((p, i) => (i===0?'M':'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ') + ` L ${width-pad},${height-pad} L ${pad},${height-pad} Z`,
             last: pts[pts.length - 1] };
  };
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <defs>
        {seeds.map((s, i) => (
          <React.Fragment key={i}>
            <linearGradient id={`${gid}-a-${i}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={colors[i]} stopOpacity="0.35"/>
              <stop offset="100%" stopColor={colors[i]} stopOpacity="0"/>
            </linearGradient>
            <filter id={`${gid}-g-${i}`} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2.5"/>
            </filter>
          </React.Fragment>
        ))}
      </defs>
      {/* grid */}
      {[0.25, 0.5, 0.75].map(f => (
        <line key={f} x1={pad} y1={height*f} x2={width-pad} y2={height*f}
          stroke="var(--line)" strokeDasharray="2 4" opacity="0.6"/>
      ))}
      {seeds.map((s, i) => {
        const b = build(s);
        return (
          <g key={i}>
            {area && <path d={b.areaD} fill={`url(#${gid}-a-${i})`} />}
            {glow && <path d={b.d} fill="none" stroke={colors[i]} strokeWidth="3" opacity="0.5" filter={`url(#${gid}-g-${i})`}/>}
            <path d={b.d} fill="none" stroke={colors[i]} strokeWidth="1.8" strokeLinejoin="round"/>
            {/* trailing dot */}
            <circle cx={b.last[0]} cy={b.last[1]} r="3" fill={colors[i]}>
              {animate && <animate attributeName="r" values="3;6;3" dur="1.8s" repeatCount="indefinite"/>}
            </circle>
            {animate && <circle cx={b.last[0]} cy={b.last[1]} r="8" fill="none" stroke={colors[i]} opacity="0.4">
              <animate attributeName="r" values="3;14;3" dur="1.8s" repeatCount="indefinite"/>
              <animate attributeName="opacity" values="0.6;0;0.6" dur="1.8s" repeatCount="indefinite"/>
            </circle>}
          </g>
        );
      })}
    </svg>
  );
}

function GlowBars({ width = 320, height = 120, seed = 3, bars = 18, color = 'var(--brand)' }) {
  const bw = width / (bars * 1.4);
  const gid = React.useId();
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id={`${gid}-bg`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="1"/>
          <stop offset="100%" stopColor={color} stopOpacity="0.25"/>
        </linearGradient>
      </defs>
      <line x1="0" y1={height-1} x2={width} y2={height-1} stroke="var(--line)" opacity="0.6"/>
      {Array.from({length: bars}).map((_, i) => {
        const h = (0.15 + rand(seed, i) * 0.8) * (height - 8);
        const x = i * (bw * 1.4) + bw * 0.2;
        const y = height - h;
        return (
          <g key={i}>
            <rect x={x} y={y} width={bw} height={h} fill={`url(#${gid}-bg)`} rx="2"/>
            <rect x={x} y={y} width={bw} height="2" fill={color} opacity="0.9"/>
          </g>
        );
      })}
    </svg>
  );
}

function RadialGauge({ value = 62, label = 'RISK', size = 180, color = 'var(--brand-2)' }) {
  const R = size * 0.38;
  const cx = size / 2, cy = size / 2;
  const C = 2 * Math.PI * R;
  const ARC = C * 0.72;
  const prog = ARC * (value / 100);
  const gid = React.useId();
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <defs>
        <linearGradient id={`${gid}-gr`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#2f7bff"/>
          <stop offset="50%" stopColor="#49e1ff"/>
          <stop offset="100%" stopColor="#ffb547"/>
        </linearGradient>
        <filter id={`${gid}-gl`}>
          <feGaussianBlur stdDeviation="3"/>
        </filter>
      </defs>
      <circle cx={cx} cy={cy} r={R} fill="none" stroke="var(--line)" strokeWidth="10"
        strokeDasharray={`${ARC} ${C}`} transform={`rotate(126 ${cx} ${cy})`} strokeLinecap="round"/>
      <circle cx={cx} cy={cy} r={R} fill="none" stroke={`url(#${gid}-gr)`} strokeWidth="10"
        strokeDasharray={`${prog} ${C}`} transform={`rotate(126 ${cx} ${cy})`} strokeLinecap="round"
        filter={`url(#${gid}-gl)`} opacity="0.9"/>
      <circle cx={cx} cy={cy} r={R} fill="none" stroke={`url(#${gid}-gr)`} strokeWidth="3"
        strokeDasharray={`${prog} ${C}`} transform={`rotate(126 ${cx} ${cy})`} strokeLinecap="round"/>
      {/* ticks */}
      {Array.from({length: 28}).map((_, i) => {
        const a = (126 + (i / 27) * 259) * Math.PI / 180;
        const x1 = cx + Math.cos(a) * (R - 14);
        const y1 = cy + Math.sin(a) * (R - 14);
        const x2 = cx + Math.cos(a) * (R - 20);
        const y2 = cy + Math.sin(a) * (R - 20);
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--fg-dim)" strokeWidth="1" opacity={i/27 < value/100 ? 0.8 : 0.25}/>;
      })}
      <text x={cx} y={cy - 2} textAnchor="middle" fontSize={size * 0.28} fontWeight="600" fill="var(--fg)">{value}</text>
      <text x={cx} y={cy + size * 0.14} textAnchor="middle" fontSize={size * 0.08} fill="var(--fg-mute)" fontFamily="var(--font-mono)" letterSpacing="0.14em">{label}</text>
    </svg>
  );
}

// 3D-looking water volume bars (耗水量 3D effect)
function Water3D({ width = 420, height = 220 }) {
  const vals = [62, 78, 54, 88, 71, 95, 83, 66, 74, 90, 82, 77];
  const labels = ['01','02','03','04','05','06','07','08','09','10','11','12'];
  const bw = (width - 40) / vals.length * 0.7;
  const gap = (width - 40) / vals.length * 0.3;
  const baseY = height - 30;
  const gid = React.useId();
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id={`${gid}-front`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#49e1ff" stopOpacity="0.95"/>
          <stop offset="100%" stopColor="#2f7bff" stopOpacity="0.4"/>
        </linearGradient>
        <linearGradient id={`${gid}-side`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#1e4f9e"/>
          <stop offset="100%" stopColor="#0a2a66"/>
        </linearGradient>
        <linearGradient id={`${gid}-top`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#9aefff"/>
          <stop offset="100%" stopColor="#49e1ff"/>
        </linearGradient>
      </defs>
      {/* base grid */}
      <line x1="20" y1={baseY} x2={width-10} y2={baseY} stroke="var(--line)" opacity="0.5"/>
      <line x1="20" y1={baseY-12} x2={width-10} y2={baseY-22} stroke="var(--line)" opacity="0.3"/>
      {vals.map((v, i) => {
        const x = 20 + i * (bw + gap);
        const h = (v / 100) * (height - 60);
        const y = baseY - h;
        const dx = 8, dy = -10; // 3D offset
        // front
        return (
          <g key={i}>
            {/* side */}
            <path d={`M${x+bw},${y} L${x+bw+dx},${y+dy} L${x+bw+dx},${baseY+dy} L${x+bw},${baseY} Z`}
                  fill={`url(#${gid}-side)`}/>
            {/* top */}
            <path d={`M${x},${y} L${x+dx},${y+dy} L${x+bw+dx},${y+dy} L${x+bw},${y} Z`}
                  fill={`url(#${gid}-top)`}/>
            {/* front */}
            <rect x={x} y={y} width={bw} height={h} fill={`url(#${gid}-front)`}/>
            {/* glow edge */}
            <rect x={x} y={y} width={bw} height="2" fill="#9aefff"/>
            <text x={x + bw/2} y={baseY + 16} textAnchor="middle" fontSize="10"
                  fill="var(--fg-mute)" fontFamily="var(--font-mono)">{labels[i]}</text>
          </g>
        );
      })}
    </svg>
  );
}

// Heatmap
function Heatmap({ rows = 7, cols = 24, seed = 11, width = 560, height = 160 }) {
  const cw = width / cols;
  const ch = height / rows;
  const gid = React.useId();
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {Array.from({length: rows}).map((_, r) =>
        Array.from({length: cols}).map((_, c) => {
          const v = rand(seed + r * 7, c);
          const color = v > 0.75 ? '#ff5a6a' : v > 0.55 ? '#ffb547' : v > 0.3 ? '#49e1ff' : '#1f3757';
          return (
            <rect key={`${r}-${c}`} x={c*cw+1} y={r*ch+1} width={cw-2} height={ch-2}
                  fill={color} opacity={0.15 + v * 0.85} rx="2"/>
          );
        })
      )}
    </svg>
  );
}

// Flow map with river + animated water droplets + station nodes
function FlowMap({ width = 800, height = 480, animate = true }) {
  const gid = React.useId();
  const riverMain = "M40,260 Q180,220 320,260 T520,290 Q640,300 760,250";
  const trib1 = "M160,100 Q200,180 260,220 T320,260";
  const trib2 = "M520,290 Q580,350 620,420";
  const stations = [
    [120,230,'S01','ok'], [230,250,'S02','ok'], [320,260,'S03','warn'],
    [430,275,'S04','ok'], [520,290,'S05','danger'], [620,270,'S06','ok'],
    [740,248,'S07','ok'], [210,150,'S08','warn'], [580,380,'S09','danger'],
    [360,400,'S10','ok'],
  ];
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id={`${gid}-terrain`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#0f1c38" stopOpacity="0.6"/>
          <stop offset="100%" stopColor="#060a14" stopOpacity="0.2"/>
        </linearGradient>
        <linearGradient id={`${gid}-river`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#2f7bff"/>
          <stop offset="100%" stopColor="#49e1ff"/>
        </linearGradient>
        <filter id={`${gid}-glow`}>
          <feGaussianBlur stdDeviation="3"/>
        </filter>
      </defs>

      {/* terrain blob */}
      <path d="M30,60 Q160,40 280,70 T500,60 Q640,50 760,90 Q800,180 770,280 T680,420 Q500,460 320,430 T80,380 Q20,280 30,60 Z"
            fill={`url(#${gid}-terrain)`} stroke="var(--line-2)" strokeWidth="1" strokeDasharray="3 6" opacity="0.8"/>

      {/* grid */}
      {Array.from({length: 12}).map((_, i) => (
        <line key={i} x1={i*70} y1="0" x2={i*70} y2={height} stroke="var(--line)" opacity="0.15"/>
      ))}

      {/* rivers */}
      <path d={riverMain} stroke="var(--line-2)" strokeWidth="16" fill="none" strokeLinecap="round" opacity="0.4"/>
      <path d={riverMain} stroke={`url(#${gid}-river)`} strokeWidth="4" fill="none" strokeLinecap="round" filter={`url(#${gid}-glow)`} opacity="0.85"/>
      <path d={riverMain} stroke="#9aefff" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
      <path d={trib1} stroke="#2f7bff" strokeWidth="2.5" fill="none" strokeLinecap="round" opacity="0.7"/>
      <path d={trib2} stroke="#2f7bff" strokeWidth="2.5" fill="none" strokeLinecap="round" opacity="0.7"/>

      {/* animated flow dots */}
      {animate && [0, 1.2, 2.4, 3.6].map((delay, i) => (
        <circle key={i} r="4" fill="#9aefff">
          <animateMotion dur="4.5s" repeatCount="indefinite" begin={`${delay}s`} path={riverMain}/>
          <animate attributeName="opacity" values="0;1;1;0" dur="4.5s" repeatCount="indefinite" begin={`${delay}s`}/>
        </circle>
      ))}

      {/* stations */}
      {stations.map(([x,y,name,st], i) => {
        const color = st === 'danger' ? '#ff5a6a' : st === 'warn' ? '#ffb547' : '#49e1ff';
        return (
          <g key={i}>
            {st === 'danger' && (
              <>
                <circle cx={x} cy={y} r="18" fill={color} opacity="0.15">
                  <animate attributeName="r" values="10;26;10" dur="2s" repeatCount="indefinite"/>
                  <animate attributeName="opacity" values="0.3;0;0.3" dur="2s" repeatCount="indefinite"/>
                </circle>
                <circle cx={x} cy={y} r="28" fill="none" stroke={color} opacity="0.4">
                  <animate attributeName="r" values="14;36;14" dur="2s" repeatCount="indefinite"/>
                  <animate attributeName="opacity" values="0.6;0;0.6" dur="2s" repeatCount="indefinite"/>
                </circle>
              </>
            )}
            <circle cx={x} cy={y} r="5" fill={color} filter={`url(#${gid}-glow)`}/>
            <circle cx={x} cy={y} r="3.5" fill={color}/>
            <circle cx={x} cy={y} r="1.5" fill="#fff"/>
            <text x={x + 10} y={y + 4} fontSize="10" fontFamily="var(--font-mono)" fill="var(--fg-soft)">{name}</text>
          </g>
        );
      })}

      {/* legend */}
      <g transform={`translate(20 ${height-24})`} fontFamily="var(--font-mono)" fontSize="10" fill="var(--fg-mute)">
        <circle cx="6" cy="0" r="4" fill="#49e1ff"/><text x="16" y="4">正常</text>
        <circle cx="66" cy="0" r="4" fill="#ffb547"/><text x="76" y="4">警戒</text>
        <circle cx="126" cy="0" r="5" fill="#ff5a6a"/><text x="136" y="4">告警</text>
        <text x="200" y="4">— 水系流向</text>
      </g>
    </svg>
  );
}

// Drop animation (tiny decorative)
function RainDrops({ count = 20 }) {
  return (
    <div style={{position:'absolute',inset:0,overflow:'hidden',pointerEvents:'none'}}>
      {Array.from({length: count}).map((_, i) => {
        const left = rand(1, i) * 100;
        const delay = rand(2, i) * 3;
        const dur = 1.5 + rand(3, i) * 2;
        return (
          <div key={i} style={{
            position:'absolute',
            left:`${left}%`, top:-10,
            width:1, height:12,
            background:'linear-gradient(180deg,transparent,#49e1ff)',
            opacity:0.5,
            animation:`drop ${dur}s linear ${delay}s infinite`
          }}/>
        );
      })}
      <style>{`@keyframes drop { 0%{transform:translateY(-20px);opacity:0} 20%{opacity:1} 100%{transform:translateY(400px);opacity:0} }`}</style>
    </div>
  );
}

Object.assign(window, { GlowLine, GlowBars, RadialGauge, Water3D, Heatmap, FlowMap, RainDrops });
