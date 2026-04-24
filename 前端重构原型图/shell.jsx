// Shell: topbar + sidebar + tweak panel
// Nav items now dispatch page changes via window.__navTo

const NAV = [
  { group: '概览', items: [
    { key: 'dash-v1',  label: '仪表盘 · v1',     nav: 'dash' },
    { key: 'dash-v2',  label: '仪表盘 · v2',     nav: 'dash' },
    { key: 'big',      label: '大屏 BigScreen',  nav: 'bigscreen' },
  ]},
  { group: '监测 Monitor', items: [
    { key: 'station',  label: '站点管理',   nav: 'station' },
    { key: 'sensor',   label: '传感器',     nav: 'sensor' },
  ]},
  { group: '数据 / 告警', items: [
    { key: 'obs',      label: '观测数据',   nav: 'obs' },
    { key: 'alarm',    label: '告警管理',   nav: 'alarm' },
    { key: 'threshold',label: '阈值规则',   nav: 'threshold' },
  ]},
  { group: 'AI 中心', items: [
    { key: 'ai-v1',    label: 'AI 命令中心 · v1', nav: 'ai' },
    { key: 'ai-v2',    label: 'AI 命令中心 · v2', nav: 'ai' },
    { key: 'plan',     label: '应急计划',         nav: 'plan' },
  ]},
  { group: '系统', items: [
    { key: 'map',      label: '地图',      nav: 'map' },
    { key: 'user',     label: '用户',      nav: 'user' },
    { key: 'role',     label: '角色',      nav: 'role' },
    { key: 'orgdept',  label: '组织 / 部门', nav: 'orgdept' },
    { key: 'log',      label: '操作日志',   nav: 'log' },
    { key: 'login',    label: '登录页',     nav: 'login' },
  ]},
];

function TopBar({ crumbs = '首页 / 仪表盘', variantLabel }) {
  return (
    <header className="wf-topbar">
      <div className="wf-brand">
        <span className="logo">水</span>
        <span>防洪应急 · 多智能体平台</span>
      </div>
      <span className="wf-crumbs">/ {crumbs}</span>
      <span className="spacer" />
      {variantLabel && <span className="chip">{variantLabel}</span>}
      <span className="chip">2026-04-19 14:22</span>
      <span className="chip">admin@ops</span>
    </header>
  );
}

function SideNav({ active, onNav }) {
  return (
    <aside className="wf-side">
      {NAV.map(g => (
        <div key={g.group}>
          <div className="group">{g.group}</div>
          {g.items.map(it => (
            <a key={it.key}
               href="#"
               className={active === it.key ? 'active' : ''}
               onClick={(e) => { e.preventDefault(); onNav(it.key); }}>
              <span className="dot" />
              <span>{it.label}</span>
            </a>
          ))}
        </div>
      ))}
    </aside>
  );
}

function TweakPanel({ dark, setDark }) {
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
    <div className={`tweak-fab ${open ? 'open' : ''}`}>
      <strong>Tweaks</strong>
      <label>
        <input
          type="checkbox"
          checked={dark}
          onChange={e => setDark(e.target.checked)}
        />
        深色大屏模式
      </label>
    </div>
  );
}

Object.assign(window, { TopBar, SideNav, TweakPanel, NAV });
