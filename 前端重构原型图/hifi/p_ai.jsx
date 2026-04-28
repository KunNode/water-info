// AI Command Center — animated agent pipeline

function AgentNode({ code, name, role, state = 'idle', progress = 0, detail, x, y, w = 180, h = 130 }) {
  return (
    <div className={`agent-card ${state}`} style={{position:'absolute',left:x,top:y,width:w,height:h}}>
      <div className="code">{code}</div>
      <div className="aname">{name}</div>
      <div className="arole">{role}</div>
      <div className="astate">
        <span className={`dot ${state==='done'?'ok':state==='run'?'warn':'off'}`}/>
        <span style={{color: state==='done'?'#4de2b3':state==='run'?'#ffc96e':'var(--fg-mute)'}}>
          {state==='done'?'已完成':state==='run'?'运行中':'待执行'}
        </span>
        {state==='run' && <span style={{marginLeft:'auto'}}>{progress}%</span>}
      </div>
      {detail && <div style={{marginTop:8,fontSize:10.5,color:'var(--fg-mute)',fontFamily:'var(--font-mono)',lineHeight:1.5}}>{detail}</div>}
      {state === 'run' && (
        <div style={{position:'absolute',left:12,right:12,bottom:10}}>
          <div className="progress" style={{height:4}}><div className="bar warn" style={{width:`${progress}%`}}/></div>
        </div>
      )}
    </div>
  );
}

function PipelineLink({ x1, y1, x2, y2, active, done }) {
  const mx = (x1 + x2) / 2;
  const d = `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
  const color = done ? '#49e1ff' : active ? '#ffb547' : '#2a3a57';
  return (
    <>
      <path d={d} stroke={color} strokeWidth="2" fill="none" opacity={done||active?0.9:0.4}
            strokeDasharray={active?'6 6':'0'}>
        {active && <animate attributeName="stroke-dashoffset" values="0;-12" dur="0.6s" repeatCount="indefinite"/>}
      </path>
      {(done || active) && (
        <path d={d} stroke={color} strokeWidth="6" fill="none" opacity="0.25"
              filter="url(#glow-pipe)"/>
      )}
      {(done || active) && (
        <circle r="3" fill={color}>
          <animateMotion dur={done?'3s':'1.8s'} repeatCount="indefinite" path={d}/>
        </circle>
      )}
    </>
  );
}

function AICenter() {
  const [msg, setMsg] = React.useState('');
  const transcript = [
    { who:'user', t:'黄陂 S05 站水位 30 分钟内上涨 0.42m，请评估风险并给出处置建议。' },
    { who:'ai',   t:'已识别为四级响应级别事件。正在调用 5 个 Agent 协作分析…' },
  ];

  return (
    <>
      <div className="page-head">
        <h1>AI 命令中心</h1>
        <span className="sub">// multi-agent pipeline · task #0419-A</span>
        <span className="sp"/>
        <span className="tag warn"><span className="dot warn"/>执行中 · 3 / 5 Agent</span>
        <button className="btn">{I.settings}编排配置</button>
        <button className="btn primary">{I.send}下发指令</button>
      </div>

      <div className="grid g-12">
        {/* Pipeline canvas */}
        <div className="card" style={{gridColumn:'span 8'}}>
          <div className="card-head">
            <span className="title">Agent 协作流水线</span>
            <span className="mono">DAG · realtime</span>
            <span className="sp"/>
            <span className="tag">自动</span>
            <span className="tag brand">人机协同</span>
          </div>
          <div style={{position:'relative',height:520,padding:16,overflow:'hidden'}}>
            <svg width="100%" height="100%" style={{position:'absolute',inset:0,pointerEvents:'none'}}>
              <defs>
                <filter id="glow-pipe"><feGaussianBlur stdDeviation="3"/></filter>
              </defs>
              <PipelineLink x1={196} y1={80}  x2={236} y2={80}  done/>
              <PipelineLink x1={416} y1={80}  x2={456} y2={170} done/>
              <PipelineLink x1={416} y1={80}  x2={456} y2={310} done/>
              <PipelineLink x1={636} y1={170} x2={676} y2={240} active/>
              <PipelineLink x1={636} y1={310} x2={676} y2={240} active/>
            </svg>

            <AgentNode x={16}  y={18}  w={180} code="A-01" name="数据采集"
              role="Data · Collector" state="done"
              detail="接入 132 站点实时流 · 缓存 2h"/>
            <AgentNode x={236} y={18}  w={180} code="A-02" name="态势识别"
              role="Insight · Detector" state="done"
              detail="识别 S05 超阈值 · 置信度 0.94"/>
            <AgentNode x={456} y={108} w={180} code="A-03" name="模拟推演"
              role="Simulation · Agent" state="done"
              detail="流域耦合模型 · 6h 预测完成"/>
            <AgentNode x={456} y={248} w={180} code="A-04" name="影响评估"
              role="Impact · Analyzer" state="done"
              detail="下游 2 乡镇 · 1.2w 人口"/>
            <AgentNode x={676} y={178} w={180} code="A-05" name="预案生成"
              role="Policy · Planner" state="run" progress={57}
              detail="生成 3 候选预案 · 排序中"/>

            {/* floating status */}
            <div style={{position:'absolute',right:14,bottom:14,fontFamily:'var(--font-mono)',fontSize:11,color:'var(--fg-mute)',display:'flex',flexDirection:'column',gap:4,background:'var(--bg-2)',padding:'10px 12px',borderRadius:8,border:'1px solid var(--line)'}}>
              <span>pipeline-id · 0419-A-dag</span>
              <span>tokens · 48.3k / 128k</span>
              <span>latency · 2.4s avg</span>
              <span>cost · $0.83</span>
            </div>
          </div>
        </div>

        {/* Chat / intent */}
        <div className="card" style={{gridColumn:'span 4',display:'flex',flexDirection:'column',maxHeight:620}}>
          <div className="card-head">
            <span className="title">指挥对话</span>
            <span className="mono">Claude · gpt-4o · 本地</span>
          </div>
          <div style={{flex:1,padding:14,overflow:'auto',display:'flex',flexDirection:'column',gap:12}}>
            {transcript.map((m,i) => (
              <div key={i} style={{
                alignSelf: m.who==='user'?'flex-end':'flex-start',
                maxWidth:'85%',
                background: m.who==='user'?'var(--grad-brand)':'var(--bg-2)',
                color: m.who==='user'?'#fff':'var(--fg)',
                padding:'10px 14px',
                borderRadius: m.who==='user'?'14px 14px 2px 14px':'14px 14px 14px 2px',
                fontSize:13,
                boxShadow: m.who==='user'?'0 8px 20px -8px rgba(47,123,255,0.5)':'none',
                border: m.who==='ai'?'1px solid var(--line)':'none'
              }}>{m.t}</div>
            ))}
            <div style={{alignSelf:'flex-start',background:'var(--bg-2)',padding:'10px 14px',borderRadius:'14px 14px 14px 2px',border:'1px solid var(--line)',fontSize:12,color:'var(--fg-soft)'}}>
              <div style={{fontFamily:'var(--font-mono)',fontSize:10,color:'var(--fg-mute)',marginBottom:4,letterSpacing:'0.1em'}}>A-05 · THINKING</div>
              <span style={{display:'inline-block',width:6,height:6,borderRadius:'50%',background:'var(--brand-2)',marginRight:3,animation:'pulse 1.2s 0s infinite'}}/>
              <span style={{display:'inline-block',width:6,height:6,borderRadius:'50%',background:'var(--brand-2)',marginRight:3,animation:'pulse 1.2s 0.2s infinite'}}/>
              <span style={{display:'inline-block',width:6,height:6,borderRadius:'50%',background:'var(--brand-2)',animation:'pulse 1.2s 0.4s infinite'}}/>
            </div>
          </div>
          <div style={{padding:12,borderTop:'1px solid var(--line)',display:'flex',gap:8}}>
            <div className="input">
              <input placeholder="向指挥中心 AI 下达指令…" value={msg} onChange={e => setMsg(e.target.value)}/>
            </div>
            <button className="btn primary icon">{I.send}</button>
          </div>
        </div>

        {/* Outcomes */}
        <div className="card" style={{gridColumn:'span 12'}}>
          <div className="card-head">
            <span className="title">候选预案（A-05 产出）</span>
            <span className="mono">ranked</span>
            <span className="sp"/>
            <button className="btn sm">对比</button>
            <button className="btn sm primary">采纳 No.1</button>
          </div>
          <div className="card-body" style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:14}}>
            {[
              ['#1','上游拦蓄 + 下游分级转移','综合代价 · 最低',92,'brand'],
              ['#2','全域预泄 + 关键桥梁封闭','风险可控 · 转移少',78,'info'],
              ['#3','维持现状 + 监测加密',     '依赖后续天气 · 较高风险',51,'warn'],
            ].map((p,i) => (
              <div key={i} style={{border:'1px solid var(--line)',borderRadius:8,padding:14,background:'var(--bg-2)',position:'relative'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                  <span className="mono" style={{fontSize:14,color: i===0?'var(--brand-2)':'var(--fg-mute)',fontWeight:600}}>{p[0]}</span>
                  <span className={`tag ${p[4]}`}>得分 {p[3]}</span>
                </div>
                <div style={{fontWeight:600,fontSize:14,marginBottom:4}}>{p[1]}</div>
                <div className="soft" style={{fontSize:12,marginBottom:10}}>{p[2]}</div>
                <div className="progress"><div className="bar" style={{width:`${p[3]}%`}}/></div>
                <div style={{display:'flex',gap:6,marginTop:10,flexWrap:'wrap'}}>
                  <span className="tag">{3-i} 步</span>
                  <span className="tag">{5+i*2} min</span>
                  <span className="tag">{12-i*3} 参与部门</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { AICenter });
