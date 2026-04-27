// Dashboard (hi-fi)

function KPICard({ label, value, unit, delta, deltaDir = 'up', seed = 1, color = 'var(--brand-2)' }) {
  return (
    <div className="card kpi">
      <div className="label">{label}</div>
      <div className="val">{value}{unit && <span className="u">{unit}</span>}</div>
      {delta && (
        <div className={`delta ${deltaDir}`}>
          <span>{deltaDir === 'up' ? '▲' : '▼'}</span>
          <span>{delta}</span>
        </div>
      )}
      <div className="spark-bg"><GlowLine height={44} seeds={[seed]} colors={[color]} glow={false} animate={false}/></div>
    </div>
  );
}

function Dashboard() {
  return (
    <>
      <div className="page-head">
        <h1>指挥仪表盘</h1>
        <span className="sub">// overview · realtime · 黄陂 — 滠水</span>
        <span className="sp"/>
        <button className="btn ghost">{I.download}导出</button>
        <button className="btn">{I.filter}筛选</button>
        <button className="btn primary">{I.plus} 新建预案</button>
      </div>

      <div className="grid g-4" style={{marginBottom:16}}>
        <KPICard label="在线站点" value="128" unit="/ 132" delta="+2 上线" deltaDir="up" seed={1} color="#49e1ff"/>
        <KPICard label="进行中告警" value="17" delta="+5 近 1h" deltaDir="down" seed={7} color="#ff5a6a"/>
        <KPICard label="24h 最大雨量" value="86" unit="mm" delta="S05 · 黄陂站" deltaDir="up" seed={3} color="#2f7bff"/>
        <KPICard label="流域风险指数" value="62" unit="/ 100" delta="等级 · 中高" deltaDir="up" seed={5} color="#ffb547"/>
      </div>

      <div className="grid g-12" style={{marginBottom:16}}>
        <div className="card" style={{gridColumn:'span 8'}}>
          <div className="card-head">
            <span className="title">流域态势 · 实时地图</span>
            <span className="mono">132 站 · 12 市</span>
            <span className="sp"/>
            <span className="tag">雨量</span>
            <span className="tag brand">水位</span>
            <span className="tag">流速</span>
          </div>
          <div style={{padding:0,height:500,position:'relative'}}>
            <FlowMap height={500}/>
            <RainDrops count={15}/>
          </div>
        </div>

        <div className="card" style={{gridColumn:'span 4',display:'flex',flexDirection:'column'}}>
          <div className="card-head">
            <span className="title">实时告警流</span>
            <span className="mono">WS · live</span>
            <span className="sp"/>
            <span className="tag danger">17 open</span>
          </div>
          <div style={{flex:1,overflow:'auto'}}>
            {[
              ['14:18','S05','超警戒水位 +0.42m','crit'],
              ['14:11','S10','1h 雨量 38mm 突破阈值','crit'],
              ['13:54','S03','传感器离线 > 10 min','warn'],
              ['13:32','S08','流速异常波动','warn'],
              ['13:05','S05','水位持续上涨 6h','warn'],
              ['12:40','S12','设备电量低','warn'],
              ['12:11','S07','告警已确认','info'],
            ].map((r, i) => (
              <div key={i} className={`alert-row ${r[3]}`}>
                <span className="time">{r[0]}</span>
                <span className="stn">{r[1]}</span>
                <span>{r[2]}</span>
                <span className={`tag ${r[3]==='crit'?'danger':r[3]==='warn'?'warn':'info'}`}>
                  {r[3]==='crit'?'CRIT':r[3]==='warn'?'WARN':'ACK'}
                </span>
                <span style={{color:'var(--fg-mute)'}}>{I.chevR}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid g-12">
        <div className="card" style={{gridColumn:'span 4'}}>
          <div className="card-head"><span className="title">24h 区域雨量</span><span className="mono">mm/hour</span></div>
          <div className="card-body"><GlowBars seed={4} bars={24} height={150} color="#2f7bff"/></div>
        </div>
        <div className="card" style={{gridColumn:'span 4'}}>
          <div className="card-head"><span className="title">关键站点水位</span><span className="mono">S05 · S10 · S08</span></div>
          <div className="card-body"><GlowLine seeds={[1,2,3]} colors={['#49e1ff','#ff5a6a','#ffb547']} height={150} animate/></div>
        </div>
        <div className="card" style={{gridColumn:'span 4'}}>
          <div className="card-head"><span className="title">AI 风险评估</span><span className="mono">realtime</span></div>
          <div className="card-body" style={{display:'flex',gap:14,alignItems:'center'}}>
            <RadialGauge value={62} size={150}/>
            <div style={{flex:1,fontSize:12}}>
              {[
                ['降雨','高',78,'#ff5a6a'],
                ['水位','中高',62,'#ffb547'],
                ['下游暴露','中',44,'#49e1ff'],
              ].map((r,i) => (
                <div key={i} style={{marginBottom:10}}>
                  <div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
                    <span className="soft">{r[0]}</span>
                    <span className="mono muted">{r[1]}</span>
                  </div>
                  <div className="progress"><div className="bar" style={{width:`${r[2]}%`,background:r[3],boxShadow:`0 0 8px ${r[3]}`}}/></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid g-12" style={{marginTop:16}}>
        <div className="card" style={{gridColumn:'span 8'}}>
          <div className="card-head"><span className="title">12 月累计耗水量 · 3D</span><span className="mono">million m³</span></div>
          <div className="card-body"><Water3D height={240}/></div>
        </div>
        <div className="card" style={{gridColumn:'span 4'}}>
          <div className="card-head"><span className="title">活跃预案</span><span className="mono">2 running</span></div>
          <div className="card-body" style={{display:'grid',gap:12}}>
            {[
              ['PLAN-0419-A','黄陂上游拦蓄 + 下游转移',57,'run'],
              ['PLAN-0419-B','S10 周边人员转移',0,'pending'],
            ].map((p,i) => (
              <div key={i} style={{border:'1px solid var(--line)',borderRadius:8,padding:12,background:'var(--bg-2)'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <span className="mono" style={{fontSize:10.5,color:'var(--fg-mute)',letterSpacing:'0.1em'}}>{p[0]}</span>
                  <span className={`tag ${p[3]==='run'?'warn':''}`}>{p[3]==='run'?'执行中':'待审批'}</span>
                </div>
                <div style={{fontWeight:600,margin:'6px 0',fontSize:13.5}}>{p[1]}</div>
                <div className="progress"><div className={`bar ${p[3]==='run'?'warn':''}`} style={{width:`${p[2]}%`}}/></div>
                <div style={{display:'flex',justifyContent:'space-between',marginTop:6,fontFamily:'var(--font-mono)',fontSize:10.5,color:'var(--fg-mute)'}}>
                  <span>{p[2]}%</span><span>ETA 28 min</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { Dashboard, KPICard });
