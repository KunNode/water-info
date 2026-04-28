// Shell: topbar, sidebar, tweaks (hi-fi)

const NAV_H = [
  { group: '概览', items: [
    { key: 'dash',    label: '指挥仪表盘', icon: 'gauge' },
    { key: 'big',     label: '大屏',       icon: 'screen' },
  ]},
  { group: '监测 Monitor', items: [
    { key: 'station', label: '站点管理',   icon: 'station', badge: '132' },
    { key: 'sensor',  label: '传感器',     icon: 'sensor',  badge: '617' },
  ]},
  { group: '数据 · 告警', items: [
    { key: 'obs',      label: '观测数据', icon: 'chart' },
    { key: 'alarm',    label: '告警管理', icon: 'bell',    badge: '17', badgeDanger: true },
    { key: 'threshold',label: '阈值规则', icon: 'shield' },
  ]},
  { group: 'AI 中心', items: [
    { key: 'ai',   label: 'AI 命令中心', icon: 'ai' },
    { key: 'plan', label: '应急预案',    icon: 'plan', badge: '2' },
  ]},
  { group: '系统', items: [
    { key: 'map',     label: '地图',        icon: 'map' },
    { key: 'user',    label: '用户',        icon: 'users' },
    { key: 'role',    label: '角色 & 权限', icon: 'key' },
    { key: 'orgdept', label: '组织部门',    icon: 'tree' },
    { key: 'log',     label: '操作日志',    icon: 'log' },
    { key: 'login',   label: '登录页',      icon: 'login' },
  ]},
];

function TopBar({ crumbs }) {
  return (
    <header className="topbar">
      <div className="brand">
        <div className="brand-mark">F</div>
        <div>
          <div className="name">FloodMind <span className="ver">v1.0</span></div>
        </div>
      </div>
      <span className="crumbs">{crumbs}</span>
      <span className="sp"/>
      <div className="top-search">
        {I.search}<span style={{flex:1}}>搜索站点、预案、用户...</span>
        <kbd>⌘K</kbd>
      </div>
      <div className="chip"><span className="ind"/>系统运行中</div>
      <div className="chip">132 站 · 17 告警</div>
      <div className="chip">2026-04-19 14:22</div>
      <div className="avatar">W</div>
    </header>
  );
}

function Side({ active, onNav }) {
  return (
    <aside className="side">
      {NAV_H.map(g => (
        <div key={g.group}>
          <div className="group-label">{g.group}</div>
          {g.items.map(it => {
            const act = active === it.key;
            return (
              <a key={it.key} className={`nav-item ${act?'active':''}`} onClick={(e) => { e.preventDefault(); onNav(it.key); }}>
                <span className="icn">{I[it.icon]}</span>
                <span>{it.label}</span>
                {it.badge && <span className={`badge ${it.badgeDanger?'danger':''}`}>{it.badge}</span>}
              </a>
            );
          })}
        </div>
      ))}
      <div style={{padding:'18px 10px',marginTop:20,borderTop:'1px solid var(--line)',display:'flex',gap:10,alignItems:'center',fontSize:11,color:'var(--fg-mute)',fontFamily:'var(--font-mono)'}}>
        <span style={{width:6,height:6,borderRadius:'50%',background:'var(--ok)',boxShadow:'0 0 8px var(--ok)'}}/>
        <span>all systems nominal</span>
      </div>
    </aside>
  );
}

function TweakFab({ dark, setDark }) {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    const onMsg = (e) => {
      if (!e.data) return;
      if (e.data.type === '__activate_edit_mode') setOpen(true);
      if (e.data.type === '__deactivate_edit_mode') setOpen(false);
    };
    window.addEventListener('message', onMsg);
    window.parent.postMessage({ type: '__edit_mode_available' }, '*');
    return () => window.removeEventListener('message', onMsg);
  }, []);
  return (
    <div className={`tweak-fab ${open?'open':''}`}>
      <span className="tk-title">Tweaks</span>
      <span style={{color:'var(--fg-soft)',display:'inline-flex',alignItems:'center',gap:8}}>
        <span>深色</span>
        <span className={`switch ${!dark?'on':''}`} onClick={() => setDark(!dark)}/>
        <span>浅色</span>
      </span>
    </div>
  );
}

Object.assign(window, { TopBar, Side, TweakFab });
