// Dashboard variations

function DashboardV1() {
  // Map-centric layout
  return (
    <>
      <div className="wf-page-head">
        <h1>仪表盘</h1>
        <span className="sub">// variant 01 · map-centric</span>
        <span className="spacer" />
        <button className="btn">导出</button>
        <button className="btn primary">新建预案</button>
      </div>

      <div className="grid g-12">
        {/* KPI row */}
        <div className="box kpi" style={{gridColumn:'span 3'}}>
          <div className="label">在线站点</div>
          <div className="val">128 / 132</div>
          <div className="delta up">↑ 2 上线</div>
        </div>
        <div className="box kpi" style={{gridColumn:'span 3'}}>
          <div className="label">进行中告警</div>
          <div className="val" style={{color:'#a14444'}}>17</div>
          <div className="delta down">↑ 5 近 1h</div>
        </div>
        <div className="box kpi" style={{gridColumn:'span 3'}}>
          <div className="label">24h 最大雨量</div>
          <div className="val">86 <span style={{fontSize:14,color:'var(--ink-mute)'}}>mm</span></div>
          <div className="delta">S05 · 黄陂站</div>
        </div>
        <div className="box kpi" style={{gridColumn:'span 3'}}>
          <div className="label">流域风险指数</div>
          <div className="val">62 <span style={{fontSize:14,color:'var(--ink-mute)'}}>/100</span></div>
          <div className="delta up">等级 · 中高</div>
        </div>

        {/* Map */}
        <div className="box" style={{gridColumn:'span 8', gridRow:'span 2'}}>
          <div className="hd">
            <span className="t">站点分布 · 实时态势</span>
            <span className="mono">132 站 · 12 市</span>
            <span className="spacer" />
            <span className="tag">雨量</span>
            <span className="tag blue">水位</span>
            <span className="tag">流速</span>
          </div>
          <div className="bd map" style={{padding:0, height:480}}>
            <MapPlaceholder />
          </div>
        </div>

        {/* Alerts */}
        <div className="box" style={{gridColumn:'span 4', gridRow:'span 2'}}>
          <div className="hd">
            <span className="t">实时告警</span>
            <span className="mono">WS · live</span>
            <span className="spacer" />
            <span className="tag danger">17 open</span>
          </div>
          <div>
            {[
              ['14:18','S05','超警戒水位 +0.42m','danger'],
              ['14:11','S10','1h 雨量 38mm 突破阈值','danger'],
              ['13:54','S03','传感器离线 > 10 min','warn'],
              ['13:32','S08','流速异常波动','warn'],
              ['13:05','S05','水位持续上涨 6h','warn'],
              ['12:40','S12','设备电量低','warn'],
              ['12:11','S07','告警已确认','blue'],
            ].map((r, i) => (
              <div key={i} className="alert-row">
                <span className="tt">{r[0]}</span>
                <span className="tag">{r[1]}</span>
                <span>{r[2]}</span>
                <span className={`tag ${r[3]==='danger'?'danger':r[3]==='warn'?'warn':'blue'}`}>
                  {r[3]==='danger'?'CRIT':r[3]==='warn'?'WARN':'ACK'}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Rainfall bars */}
        <div className="box" style={{gridColumn:'span 4'}}>
          <div className="hd">
            <span className="t">24h 区域雨量</span>
            <span className="mono">mm / hour</span>
          </div>
          <div className="bd">
            <BarChartPH seed={4} bars={24} height={120} />
          </div>
        </div>
        <div className="box" style={{gridColumn:'span 4'}}>
          <div className="hd">
            <span className="t">关键站点水位趋势</span>
            <span className="mono">S05 · S10 · S08</span>
          </div>
          <div className="bd">
            <LineChartPH seeds={[1,2,3]} colors={['var(--blue)','#a14444','var(--ink-soft)']} height={120} />
          </div>
        </div>
        <div className="box" style={{gridColumn:'span 4'}}>
          <div className="hd">
            <span className="t">AI 智能体活动</span>
            <span className="mono">last 6h</span>
          </div>
          <div className="bd" style={{display:'flex',gap:14,alignItems:'center'}}>
            <GaugePH value={62} label="RISK" />
            <div style={{flex:1, fontSize:12}}>
              <div style={{display:'flex',justifyContent:'space-between',margin:'4px 0'}}>
                <span>预案生成</span><span className="mono">3</span>
              </div>
              <div style={{display:'flex',justifyContent:'space-between',margin:'4px 0'}}>
                <span>风险评估</span><span className="mono">14</span>
              </div>
              <div style={{display:'flex',justifyContent:'space-between',margin:'4px 0'}}>
                <span>资源调度</span><span className="mono">2</span>
              </div>
              <div style={{display:'flex',justifyContent:'space-between',margin:'4px 0'}}>
                <span>通知下发</span><span className="mono">21</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function DashboardV2() {
  // Alert & timeline centric
  return (
    <>
      <div className="wf-page-head">
        <h1>仪表盘</h1>
        <span className="sub">// variant 02 · alert + timeline centric</span>
        <span className="spacer" />
        <button className="btn">切换视图</button>
        <button className="btn primary">应急总览</button>
      </div>

      <div className="grid g-12">
        {/* Status band */}
        <div className="box" style={{gridColumn:'span 12'}}>
          <div className="bd" style={{display:'flex',gap:0,padding:0}}>
            {[
              ['流域状态','中高风险','62/100','var(--yellow)'],
              ['降雨强度','暴雨 红色','38 mm/h','#d88a8a'],
              ['超警站点','7 / 132','S05 最高','var(--blue)'],
              ['活跃预案','2','第 4 轮执行中','var(--blue)'],
              ['响应时间','4.2 min','p50 SLA','var(--ink-soft)'],
            ].map((c,i) => (
              <div key={i} style={{flex:1, padding:'16px 18px', borderLeft:i?'1px solid var(--line-soft)':'none'}}>
                <div style={{fontFamily:'var(--font-mono)',fontSize:10.5,color:'var(--ink-mute)',letterSpacing:'0.08em',textTransform:'uppercase'}}>{c[0]}</div>
                <div style={{fontSize:22,fontWeight:600,margin:'6px 0'}}>{c[1]}</div>
                <div style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-soft)'}}>
                  <span style={{display:'inline-block',width:8,height:8,background:c[3],borderRadius:2,marginRight:6}}/>
                  {c[2]}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Big timeline */}
        <div className="box" style={{gridColumn:'span 8'}}>
          <div className="hd">
            <span className="t">事件时间轴 · 今日</span>
            <span className="mono">04-19 · 00:00 → now</span>
            <span className="spacer" />
            <div className="tabs" style={{margin:0, border:'none'}}>
              <button className="active">告警</button>
              <button>预案</button>
              <button>操作</button>
            </div>
          </div>
          <div className="bd">
            {/* horizontal timeline */}
            <svg viewBox="0 0 900 180" width="100%" height="180">
              <line x1="30" y1="120" x2="870" y2="120" stroke="var(--line)" />
              {Array.from({length:13}).map((_,i) => {
                const x = 30 + i * 70;
                return (
                  <g key={i}>
                    <line x1={x} y1="115" x2={x} y2="125" stroke="var(--line)" />
                    <text x={x} y="145" fontSize="10" fontFamily="var(--font-mono)"
                          textAnchor="middle" fill="var(--ink-mute)">{String(i*2).padStart(2,'0')}:00</text>
                  </g>
                );
              })}
              {/* events */}
              {[
                [180, 'warn', 'S03 离线'],
                [300, 'warn', '雨量↑'],
                [440, 'danger', 'S05 超警'],
                [520, 'blue', '预案 A'],
                [610, 'danger', 'S10 爆发'],
                [680, 'blue', '调度'],
                [760, 'warn', 'S08 波动'],
              ].map((e,i) => {
                const [x, kind, lbl] = e;
                const color = kind==='danger'?'#d88a8a':kind==='warn'?'#f5d76e':'var(--blue)';
                return (
                  <g key={i}>
                    <line x1={x} y1="120" x2={x} y2={50 + (i%3)*14} stroke="var(--line-soft)" />
                    <rect x={x-32} y={38 + (i%3)*14} width="64" height="16" fill={color} stroke="var(--line)" />
                    <text x={x} y={50 + (i%3)*14} fontSize="10" textAnchor="middle" fill="#1a1a1a">{lbl}</text>
                    <circle cx={x} cy="120" r="4" fill={color} stroke="var(--line)" />
                  </g>
                );
              })}
              <line x1="760" y1="30" x2="760" y2="155" stroke="var(--blue)" strokeDasharray="3 3" />
              <text x="770" y="30" fontSize="10" fontFamily="var(--font-mono)" fill="var(--blue)">NOW 14:22</text>
            </svg>

            <div className="grid g-3" style={{marginTop:14}}>
              <div>
                <div style={{fontFamily:'var(--font-mono)',fontSize:10,color:'var(--ink-mute)'}}>降雨 (mm/h)</div>
                <BarChartPH seed={2} bars={24} height={70} />
              </div>
              <div>
                <div style={{fontFamily:'var(--font-mono)',fontSize:10,color:'var(--ink-mute)'}}>水位 (m)</div>
                <LineChartPH seeds={[5]} colors={['var(--blue)']} height={70} />
              </div>
              <div>
                <div style={{fontFamily:'var(--font-mono)',fontSize:10,color:'var(--ink-mute)'}}>告警数</div>
                <BarChartPH seed={7} bars={24} height={70} color="#d88a8a" />
              </div>
            </div>
          </div>
        </div>

        {/* Active plans */}
        <div className="box" style={{gridColumn:'span 4'}}>
          <div className="hd">
            <span className="t">活跃预案</span>
            <span className="mono">2 running</span>
          </div>
          <div className="bd" style={{display:'flex',flexDirection:'column',gap:12}}>
            {[
              ['PLAN-0419-A','黄陂流域上游拦截','执行中','step 4/7','var(--blue)'],
              ['PLAN-0419-B','S10 周边人员转移','待审批','0/5','var(--yellow)'],
            ].map((p,i) => (
              <div key={i} style={{border:'1px solid var(--line-soft)', borderRadius:4, padding:12}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <span style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)'}}>{p[0]}</span>
                  <span className="tag" style={{background:p[4],color:'#1a1a1a'}}>{p[2]}</span>
                </div>
                <div style={{fontWeight:600, margin:'6px 0'}}>{p[1]}</div>
                <div style={{height:6, background:'var(--line-soft)', borderRadius:3, overflow:'hidden'}}>
                  <div style={{height:'100%', width: p[3]==='0/5'?'0%':'57%', background:'var(--blue)'}} />
                </div>
                <div style={{display:'flex',justifyContent:'space-between',marginTop:6,fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)'}}>
                  <span>{p[3]}</span><span>ETA 28 min</span>
                </div>
              </div>
            ))}
            <button className="btn" style={{alignSelf:'flex-start'}}>+ 查看全部 14 个历史预案</button>
          </div>
        </div>

        {/* Alert stream */}
        <div className="box" style={{gridColumn:'span 5'}}>
          <div className="hd">
            <span className="t">告警流</span>
            <span className="mono">ws · live</span>
            <span className="spacer" />
            <span className="tag danger">17</span>
            <span className="tag warn">8</span>
            <span className="tag blue">3</span>
          </div>
          <div>
            {[
              ['14:18','S05','超警戒水位 +0.42m','CRIT'],
              ['14:11','S10','1h 雨量 38mm > 阈值','CRIT'],
              ['13:54','S03','传感器离线 > 10 min','WARN'],
              ['13:32','S08','流速异常波动','WARN'],
              ['13:05','S05','水位持续上涨 6h','WARN'],
            ].map((r, i) => (
              <div key={i} className="alert-row">
                <span className="tt">{r[0]}</span>
                <span className="tag">{r[1]}</span>
                <span>{r[2]}</span>
                <span className={`tag ${r[3]==='CRIT'?'danger':r[3]==='WARN'?'warn':'blue'}`}>{r[3]}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Mini map */}
        <div className="box" style={{gridColumn:'span 4'}}>
          <div className="hd">
            <span className="t">热点站点</span>
            <span className="mono">top 5 risk</span>
          </div>
          <div className="bd map" style={{padding:0, height:240}}>
            <MapPlaceholder />
          </div>
        </div>

        {/* Resource pool */}
        <div className="box" style={{gridColumn:'span 3'}}>
          <div className="hd">
            <span className="t">资源池</span>
            <span className="mono">available</span>
          </div>
          <div className="bd" style={{display:'grid',gap:10}}>
            {[
              ['抢险队伍','12 / 18'],
              ['泵车','8 / 14'],
              ['沙袋储备','1240 / 2000'],
              ['应急广播','42 / 50'],
            ].map((r,i) => (
              <div key={i}>
                <div style={{display:'flex',justifyContent:'space-between',fontSize:12}}>
                  <span>{r[0]}</span><span className="mono" style={{color:'var(--ink-mute)'}}>{r[1]}</span>
                </div>
                <div style={{height:5,background:'var(--line-soft)',borderRadius:3,marginTop:4,overflow:'hidden'}}>
                  <div style={{height:'100%',width: `${30+i*15}%`,background:'var(--blue)'}}/>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { DashboardV1, DashboardV2 });
