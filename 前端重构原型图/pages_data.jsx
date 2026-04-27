// Observation data page

function ObservationPage() {
  return (
    <>
      <div className="wf-page-head">
        <h1>观测数据</h1>
        <span className="sub">// data / observation</span>
        <span className="spacer"/>
        <button className="btn">导出 CSV</button>
        <button className="btn">订阅</button>
      </div>

      <div className="box" style={{marginBottom:14, padding:16}}>
        <div style={{display:'grid',gridTemplateColumns:'repeat(5, 1fr)',gap:12}}>
          <div>
            <div style={{fontSize:11,color:'var(--ink-mute)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em',marginBottom:4}}>站点</div>
            <Input value="S005 · 黄陂五号 · 水位"/>
          </div>
          <div>
            <div style={{fontSize:11,color:'var(--ink-mute)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em',marginBottom:4}}>指标</div>
            <Input value="水位 · 雨量 · 流速"/>
          </div>
          <div>
            <div style={{fontSize:11,color:'var(--ink-mute)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em',marginBottom:4}}>时间范围</div>
            <Input value="2026-04-18 00:00 → 2026-04-19 14:22"/>
          </div>
          <div>
            <div style={{fontSize:11,color:'var(--ink-mute)',fontFamily:'var(--font-mono)',textTransform:'uppercase',letterSpacing:'0.06em',marginBottom:4}}>聚合</div>
            <Input value="5 min 平均"/>
          </div>
          <div style={{display:'flex',alignItems:'end',gap:8}}>
            <button className="btn primary">查询</button>
            <button className="btn">重置</button>
          </div>
        </div>
      </div>

      <div className="grid g-12" style={{marginBottom:14}}>
        <div className="box" style={{gridColumn:'span 8'}}>
          <div className="hd">
            <span className="t">趋势图 · 水位 / 雨量</span>
            <span className="mono">38h · 5min</span>
            <span className="spacer"/>
            <div className="tabs" style={{margin:0,border:'none'}}>
              <button className="active">折线</button>
              <button>面积</button>
              <button>柱状</button>
            </div>
          </div>
          <div className="bd">
            <LineChartPH seeds={[1,5,9]} colors={['var(--blue)','#d88a8a','var(--ink-soft)']} height={280}/>
            <div style={{display:'flex',gap:16,marginTop:10,fontFamily:'var(--font-mono)',fontSize:11}}>
              <span><span style={{display:'inline-block',width:10,height:2,background:'var(--blue)',verticalAlign:'middle',marginRight:6}}/>水位 m</span>
              <span><span style={{display:'inline-block',width:10,height:2,background:'#d88a8a',verticalAlign:'middle',marginRight:6}}/>雨量 mm/h</span>
              <span><span style={{display:'inline-block',width:10,height:2,background:'var(--ink-soft)',verticalAlign:'middle',marginRight:6}}/>流速 m/s</span>
            </div>
          </div>
        </div>

        <div className="box" style={{gridColumn:'span 4'}}>
          <div className="hd"><span className="t">统计摘要</span><span className="mono">window</span></div>
          <div className="bd" style={{display:'grid',gap:10,fontSize:13}}>
            {[
              ['最大水位','4.82 m','14:18'],
              ['最小水位','3.96 m','04-18 03:10'],
              ['累计雨量','86 mm','38h'],
              ['均值水位','4.31 m','—'],
              ['超警时长','2h 14m','> 4.5m'],
              ['采样点','4,560','-'],
            ].map((r,i) => (
              <div key={i} style={{display:'flex',justifyContent:'space-between',borderBottom: i<5?'1px dashed var(--line-soft)':'none',paddingBottom:6}}>
                <span>{r[0]}</span>
                <span style={{fontWeight:600}}>{r[1]}</span>
                <span className="mono" style={{color:'var(--ink-mute)',width:90,textAlign:'right'}}>{r[2]}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <Table
        cols={['时间','站点','水位(m)','雨量(mm/h)','流速(m/s)','水温(℃)','状态']}
        rows={Array.from({length:6}).map((_,i) => [
          `14:${22-i*5 < 10 ? '0'+(22-i*5) : 22-i*5}:00`,
          'S005',
          (4.82 - i*0.04).toFixed(2),
          (38 - i*4).toString(),
          (1.2 + i*0.05).toFixed(2),
          '18.4',
          i<2 ? <span><StatusDot state="error"/>超警</span> : <span><StatusDot state="ok"/>正常</span>
        ])}
        dense
      />
      <Pagination/>
    </>
  );
}

Object.assign(window, { ObservationPage });
