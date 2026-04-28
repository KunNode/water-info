// Emergency Plan page + Map page

function PlanPage() {
  return (
    <>
      <div className="wf-page-head">
        <h1>应急计划</h1>
        <span className="sub">// ai / plan · 2 running · 14 历史</span>
        <span className="spacer"/>
        <button className="btn">模板库</button>
        <button className="btn primary">+ AI 生成预案</button>
      </div>

      <Toolbar>
        <SearchField placeholder="预案编号 / 关键词" w={260}/>
        <Select label="状态" value="全部"/>
        <Select label="流域" value="全部"/>
        <Select label="时间" value="本周"/>
        <button className="btn">查询</button>
      </Toolbar>

      <div className="grid g-3" style={{marginBottom:14}}>
        {[
          ['PLAN-0419-A','黄陂上游拦蓄 + 下游转移','执行中 · 步 4/7',57,'run'],
          ['PLAN-0419-B','S10 周边人员转移','待审批 · 0/5',0,'pending'],
          ['PLAN-0418-C','木兰湖溢洪排查','已完成',100,'done'],
        ].map((p,i) => (
          <div key={i} className="box" style={{padding:16}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
              <span style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)'}}>{p[0]}</span>
              <span className={`tag ${p[4]==='run'?'warn':p[4]==='pending'?'':'blue'}`}>{p[2]}</span>
            </div>
            <div style={{fontWeight:600,fontSize:15,margin:'8px 0'}}>{p[1]}</div>
            <div style={{height:6,background:'var(--line-soft)',borderRadius:3,overflow:'hidden'}}>
              <div style={{height:'100%',width:`${p[3]}%`,background:p[4]==='done'?'var(--blue)':'var(--yellow)'}}/>
            </div>
            <div style={{display:'flex',justifyContent:'space-between',marginTop:8,fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)'}}>
              <span>由 AI 生成 · 14:20</span><span>ETA 28m</span>
            </div>
          </div>
        ))}
      </div>

      <div className="box">
        <div className="hd">
          <span className="t">PLAN-0419-A · 详情</span>
          <span className="mono">draft → approved → running</span>
          <span className="spacer"/>
          <button className="btn">克隆</button>
          <button className="btn">导出 PDF</button>
          <button className="btn primary">▶ 继续执行</button>
        </div>
        <div className="bd" style={{display:'grid',gridTemplateColumns:'1.4fr 1fr',gap:20}}>
          <div>
            <div style={{fontFamily:'var(--font-mono)',fontSize:10.5,color:'var(--ink-mute)',letterSpacing:'0.08em',textTransform:'uppercase',marginBottom:10}}>
              执行步骤 · 7
            </div>
            {[
              ['01','上游水库预泄','水利局','10 min','done'],
              ['02','S05/S10 断面加固','抢险 A 队','30 min','done'],
              ['03','下游 3 镇广播预警','应急办','5 min','done'],
              ['04','低洼区域人员转移','街道办','60 min','run'],
              ['05','抢险队伍集结 B/C','抢险队','—','next'],
              ['06','泵车调度 · 8 辆','交通局','—','queued'],
              ['07','持续监测与复盘','监控组','—','queued'],
            ].map((s,i) => (
              <div key={i} style={{display:'grid',gridTemplateColumns:'40px 1fr 120px 80px 80px',gap:10,padding:'10px 0',borderBottom:'1px dashed var(--line-soft)',alignItems:'center',fontSize:13}}>
                <span style={{fontFamily:'var(--font-mono)',color:'var(--ink-mute)'}}>{s[0]}</span>
                <span style={{fontWeight: s[4]==='run'?600:400}}>{s[1]}</span>
                <span style={{color:'var(--ink-soft)',fontSize:12}}>{s[2]}</span>
                <span style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)'}}>{s[3]}</span>
                <span className={`tag ${s[4]==='done'?'blue':s[4]==='run'?'warn':''}`}>{s[4]}</span>
              </div>
            ))}
          </div>
          <div>
            <div style={{fontFamily:'var(--font-mono)',fontSize:10.5,color:'var(--ink-mute)',letterSpacing:'0.08em',textTransform:'uppercase',marginBottom:10}}>
              资源分配
            </div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
              {[
                ['水利局','lead'],
                ['应急办','co-lead'],
                ['气象局','data'],
                ['交通局','support'],
                ['抢险 A / B / C','exec'],
                ['泵车 ×8','exec'],
                ['沙袋 ×1200','materials'],
                ['广播 ×42','comms'],
              ].map((r,i) => (
                <div key={i} style={{border:'1px solid var(--line-soft)',padding:'8px 10px',borderRadius:3,fontSize:12,display:'flex',justifyContent:'space-between'}}>
                  <span>{r[0]}</span>
                  <span className="mono" style={{color:'var(--ink-mute)'}}>{r[1]}</span>
                </div>
              ))}
            </div>
            <div style={{marginTop:18,padding:12,background:'var(--paper-2)',borderRadius:4}}>
              <div style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)',marginBottom:6}}>执行影响预测</div>
              <div style={{fontSize:13,lineHeight:1.7}}>
                预计完成 <strong>28 min</strong><br/>
                影响人口 <strong>12,480 人</strong> · 3 镇<br/>
                避免潜在损失 ≈ <strong>¥ 3.2 亿</strong>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function MapPage() {
  return (
    <>
      <div className="wf-page-head">
        <h1>地图</h1>
        <span className="sub">// map · leaflet · 站点分布</span>
        <span className="spacer"/>
        <button className="btn">图层</button>
        <button className="btn">轨迹</button>
        <button className="btn primary">全屏</button>
      </div>

      <div className="grid" style={{gridTemplateColumns:'280px 1fr',gap:14}}>
        <div className="box">
          <div className="hd"><span className="t">图层 / 过滤</span></div>
          <div className="bd" style={{display:'grid',gap:12,fontSize:13}}>
            <div>
              <div style={{fontFamily:'var(--font-mono)',fontSize:10.5,color:'var(--ink-mute)',marginBottom:6}}>BASE LAYER</div>
              {['地形 / terrain','卫星 / satellite','简约 / light'].map((l,i) => (
                <label key={i} style={{display:'flex',alignItems:'center',gap:6,padding:'4px 0'}}>
                  <input type="radio" name="base" defaultChecked={i===0}/>{l}
                </label>
              ))}
            </div>
            <div>
              <div style={{fontFamily:'var(--font-mono)',fontSize:10.5,color:'var(--ink-mute)',marginBottom:6}}>OVERLAY</div>
              {['水系 / 河道','雨量热力','水位站点','流速矢量','行政边界','人口分布'].map((l,i) => (
                <label key={i} style={{display:'flex',alignItems:'center',gap:6,padding:'4px 0'}}>
                  <input type="checkbox" defaultChecked={i<4}/>{l}
                </label>
              ))}
            </div>
            <div>
              <div style={{fontFamily:'var(--font-mono)',fontSize:10.5,color:'var(--ink-mute)',marginBottom:6}}>状态过滤</div>
              {['在线 128','警戒 8','告警 4','离线 21'].map((l,i) => (
                <label key={i} style={{display:'flex',alignItems:'center',gap:6,padding:'4px 0'}}>
                  <input type="checkbox" defaultChecked/>{l}
                </label>
              ))}
            </div>
          </div>
        </div>

        <div className="box">
          <div className="hd">
            <span className="t">流域态势</span>
            <span className="mono">30.8°N 114.4°E · z=10</span>
            <span className="spacer"/>
            <span className="tag">雨量</span>
            <span className="tag blue">水位</span>
          </div>
          <div className="bd map" style={{padding:0,height:600}}>
            <MapPlaceholder/>
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { PlanPage, MapPage });
