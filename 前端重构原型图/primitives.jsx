// Shared table + form wireframe primitives

function Toolbar({ children }) {
  return <div style={{display:'flex',gap:8,alignItems:'center',marginBottom:12,flexWrap:'wrap'}}>{children}</div>;
}

function SearchField({ placeholder = '搜索...', w = 220 }) {
  return (
    <div style={{display:'inline-flex',alignItems:'center',gap:6,border:'1.5px solid var(--line)',borderRadius:3,padding:'5px 10px',background:'var(--paper-card)',width:w,fontSize:12,color:'var(--ink-mute)'}}>
      <span style={{fontFamily:'var(--font-mono)'}}>⌕</span>
      <span>{placeholder}</span>
    </div>
  );
}

function Select({ label, value, w = 140 }) {
  return (
    <div style={{display:'inline-flex',alignItems:'center',gap:6,border:'1.5px solid var(--line)',borderRadius:3,padding:'5px 10px',background:'var(--paper-card)',width:w,fontSize:12}}>
      <span style={{color:'var(--ink-mute)'}}>{label}:</span>
      <span style={{fontWeight:500}}>{value}</span>
      <span style={{marginLeft:'auto',color:'var(--ink-mute)'}}>▾</span>
    </div>
  );
}

function Table({ cols, rows, dense }) {
  return (
    <div className="box">
      <table style={{width:'100%',borderCollapse:'collapse',fontSize:13}}>
        <thead>
          <tr style={{background:'var(--paper-2)',textAlign:'left'}}>
            {cols.map((c,i) => (
              <th key={i} style={{padding: dense?'8px 12px':'10px 14px',fontWeight:600,fontSize:12,fontFamily:'var(--font-mono)',color:'var(--ink-soft)',letterSpacing:'0.04em',textTransform:'uppercase',borderBottom:'1.5px solid var(--line)'}}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r,i) => (
            <tr key={i} style={{borderBottom:'1px solid var(--line-soft)'}}>
              {r.map((cell,j) => (
                <td key={j} style={{padding: dense?'8px 12px':'11px 14px',verticalAlign:'middle'}}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Pagination() {
  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginTop:12,fontSize:12,color:'var(--ink-mute)',fontFamily:'var(--font-mono)'}}>
      <span>共 284 条 · 每页 20</span>
      <div style={{display:'flex',gap:4}}>
        <button className="btn" style={{padding:'4px 10px'}}>‹</button>
        {['1','2','3','...','15'].map((n,i) => (
          <button key={i} className={i===0?'btn primary':'btn'} style={{padding:'4px 10px'}}>{n}</button>
        ))}
        <button className="btn" style={{padding:'4px 10px'}}>›</button>
      </div>
    </div>
  );
}

function FormRow({ label, children, hint }) {
  return (
    <div style={{display:'grid',gridTemplateColumns:'120px 1fr',gap:12,alignItems:'start',padding:'10px 0',borderBottom:'1px dashed var(--line-soft)'}}>
      <label style={{fontSize:12,color:'var(--ink-soft)',paddingTop:6}}>{label}</label>
      <div>
        {children}
        {hint && <div style={{fontSize:11,color:'var(--ink-mute)',marginTop:4,fontFamily:'var(--font-mono)'}}>{hint}</div>}
      </div>
    </div>
  );
}

function Input({ value, w = '100%', placeholder }) {
  return (
    <div style={{border:'1.5px solid var(--line)',borderRadius:3,padding:'6px 10px',background:'var(--paper-card)',width:w,fontSize:13,minHeight:32}}>
      {value || <span style={{color:'var(--ink-mute)'}}>{placeholder || '...'}</span>}
    </div>
  );
}

function StatusDot({ state }) {
  const color = state==='ok'||state==='online'||state==='active' ? 'var(--blue)'
              : state==='warn' ? 'var(--yellow)'
              : state==='error'||state==='offline' ? '#d88a8a'
              : 'var(--line-soft)';
  return <span style={{display:'inline-block',width:8,height:8,borderRadius:'50%',background:color,border:'1px solid var(--line)',verticalAlign:'middle',marginRight:6}}/>;
}

Object.assign(window, { Toolbar, SearchField, Select, Table, Pagination, FormRow, Input, StatusDot });
