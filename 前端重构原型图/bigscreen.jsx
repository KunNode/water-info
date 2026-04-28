// BigScreen wireframe - 1920x1080

function BigScreen() {
  return (
    <div className="bigscreen">
      <div className="bs-head">
        <div className="wf-brand" style={{fontSize:20}}>
          <span className="logo" style={{width:34,height:34,fontSize:16}}>水</span>
          <span>防洪应急 · 多智能体指挥中心</span>
        </div>
        <span className="meta">|  流域：黄陂 — 滠水  ·  运行中</span>
        <span style={{flex:1}}/>
        <span className="meta">2026-04-19 星期日  14:22:08</span>
        <span className="tag danger" style={{fontSize:13,padding:'4px 10px'}}>红色预警</span>
      </div>

      <div className="bs-grid">
        {/* Left column */}
        <div style={{display:'grid',gap:18,gridTemplateRows:'auto auto 1fr'}}>
          <div className="box">
            <div className="hd"><span className="t">关键指标</span><span className="mono">realtime</span></div>
            <div className="bd" style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
              {[
                ['在线站点','128/132'],
                ['告警·进行中','17'],
                ['24h 最大雨量','86 mm'],
                ['流域风险','62 / 中高'],
              ].map((k,i) => (
                <div key={i} style={{border:'1px solid var(--line-soft)',padding:10}}>
                  <div style={{fontSize:11,fontFamily:'var(--font-mono)',color:'var(--ink-mute)',letterSpacing:'0.08em',textTransform:'uppercase'}}>{k[0]}</div>
                  <div style={{fontSize:26,fontWeight:600,marginTop:4}}>{k[1]}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="box">
            <div className="hd"><span className="t">24h 区域雨量 · 热力</span><span className="mono">mm/h</span></div>
            <div className="bd"><BarChartPH seed={11} bars={24} height={130} color="var(--blue)" /></div>
          </div>

          <div className="box">
            <div className="hd"><span className="t">告警流</span><span className="mono">ws · live</span></div>
            <div>
              {[
                ['14:18','S05','超警戒水位 +0.42m','CRIT'],
                ['14:11','S10','1h 雨量 38mm > 阈值','CRIT'],
                ['13:54','S03','传感器离线 > 10m','WARN'],
                ['13:32','S08','流速异常波动','WARN'],
                ['13:05','S05','水位持续上涨 6h','WARN'],
                ['12:40','S12','设备电量低','WARN'],
              ].map((r,i) => (
                <div key={i} className="alert-row" style={{fontSize:13}}>
                  <span className="tt">{r[0]}</span>
                  <span className="tag">{r[1]}</span>
                  <span>{r[2]}</span>
                  <span className={`tag ${r[3]==='CRIT'?'danger':'warn'}`}>{r[3]}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Center column - big map */}
        <div style={{display:'grid',gap:18,gridTemplateRows:'1fr auto'}}>
          <div className="box">
            <div className="hd">
              <span className="t">流域态势地图</span>
              <span className="mono">132 站 · 12 市</span>
              <span className="spacer" />
              <span className="tag">雨量</span>
              <span className="tag blue">水位</span>
              <span className="tag">流速</span>
            </div>
            <div className="bd map" style={{padding:0, height:560}}>
              <MapPlaceholder />
            </div>
          </div>

          <div className="box">
            <div className="hd"><span className="t">智能体流水线 · run #218</span><span className="mono">elapsed 00:07.1</span></div>
            <div className="bd" style={{padding:0}}>
              <div className="pipeline">
                {[
                  ['Supervisor','done','2.1s'],
                  ['DataAnalyst','done','3.8s'],
                  ['RiskAssessor','done','2.1s'],
                  ['PlanGenerator','run','66%'],
                  ['ResourceDispatcher','','queued'],
                  ['NotificationAgent','','queued'],
                ].map((a,i) => (
                  <div key={i} className={`agent-node ${a[1]}`} style={{minHeight:110}}>
                    <div className="n">AGENT 0{i+1}</div>
                    <div className="name" style={{fontSize:13}}>{a[0]}</div>
                    <div className="state">{a[2]}</div>
                    <div className="arr"/>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Right column */}
        <div style={{display:'grid',gap:18,gridTemplateRows:'auto auto 1fr'}}>
          <div className="box">
            <div className="hd"><span className="t">风险评估</span><span className="mono">AI</span></div>
            <div className="bd" style={{display:'flex',alignItems:'center',gap:14}}>
              <GaugePH value={62} label="RISK 62" />
              <div style={{flex:1,fontSize:13}}>
                <div style={{display:'flex',justifyContent:'space-between'}}><span>降雨</span><span className="mono">高</span></div>
                <div style={{height:6,background:'var(--line-soft)',margin:'4px 0 10px'}}><div style={{height:'100%',width:'78%',background:'#d88a8a'}}/></div>
                <div style={{display:'flex',justifyContent:'space-between'}}><span>水位</span><span className="mono">中高</span></div>
                <div style={{height:6,background:'var(--line-soft)',margin:'4px 0 10px'}}><div style={{height:'100%',width:'62%',background:'var(--yellow)'}}/></div>
                <div style={{display:'flex',justifyContent:'space-between'}}><span>暴露</span><span className="mono">中</span></div>
                <div style={{height:6,background:'var(--line-soft)',margin:'4px 0 0'}}><div style={{height:'100%',width:'44%',background:'var(--blue)'}}/></div>
              </div>
            </div>
          </div>

          <div className="box">
            <div className="hd"><span className="t">活跃预案</span><span className="mono">2 running</span></div>
            <div className="bd" style={{display:'grid',gap:10}}>
              {[
                ['PLAN-0419-A','黄陂上游拦蓄 + 下游转移','57%'],
                ['PLAN-0419-B','S10 周边人员转移','0%'],
              ].map((p,i) => (
                <div key={i} style={{border:'1px solid var(--line-soft)', padding:10}}>
                  <div style={{display:'flex',justifyContent:'space-between',fontSize:12,fontFamily:'var(--font-mono)',color:'var(--ink-mute)'}}>
                    <span>{p[0]}</span><span>{p[2]}</span>
                  </div>
                  <div style={{fontWeight:600,margin:'4px 0'}}>{p[1]}</div>
                  <div style={{height:5,background:'var(--line-soft)'}}><div style={{height:'100%',width:p[2],background:'var(--blue)'}}/></div>
                </div>
              ))}
            </div>
          </div>

          <div className="box">
            <div className="hd"><span className="t">资源调度</span><span className="mono">available / total</span></div>
            <div className="bd" style={{display:'grid',gap:10,fontSize:13}}>
              {[
                ['抢险队伍',12,18],
                ['泵车',8,14],
                ['沙袋储备',1240,2000],
                ['应急广播',42,50],
                ['通信车',6,8],
              ].map((r,i) => (
                <div key={i}>
                  <div style={{display:'flex',justifyContent:'space-between'}}>
                    <span>{r[0]}</span>
                    <span className="mono" style={{color:'var(--ink-mute)'}}>{r[1]} / {r[2]}</span>
                  </div>
                  <div style={{height:6,background:'var(--line-soft)',marginTop:4}}>
                    <div style={{height:'100%',width: `${(r[1]/r[2])*100}%`,background:'var(--blue)'}}/>
                  </div>
                </div>
              ))}
              <div style={{marginTop:6,borderTop:'1px dashed var(--line-soft)',paddingTop:10}}>
                <div style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)',marginBottom:6}}>TRENDS · 72h</div>
                <LineChartPH seeds={[2,6]} colors={['var(--blue)','var(--ink-soft)']} height={70}/>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { BigScreen });
