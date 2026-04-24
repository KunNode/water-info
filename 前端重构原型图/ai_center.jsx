// AI Command Center variations

const AGENTS = [
  { n: '01', name: 'Supervisor',        role: '总调度' },
  { n: '02', name: 'DataAnalyst',       role: '数据分析' },
  { n: '03', name: 'RiskAssessor',      role: '风险评估' },
  { n: '04', name: 'PlanGenerator',     role: '预案生成' },
  { n: '05', name: 'ResourceDispatcher',role: '资源调度' },
  { n: '06', name: 'NotificationAgent', role: '通知下发' },
];

function AiCenterV1() {
  // Chat + timeline side-by-side
  return (
    <>
      <div className="wf-page-head">
        <h1>AI 命令中心</h1>
        <span className="sub">// variant 01 · chat + timeline</span>
        <span className="spacer" />
        <span className="tag blue">session #4281</span>
        <button className="btn">历史会话</button>
        <button className="btn primary">新会话</button>
      </div>

      <div className="grid" style={{gridTemplateColumns:'1.1fr 1fr 0.9fr', gap:14}}>
        {/* Chat */}
        <div className="box" style={{display:'flex',flexDirection:'column',minHeight:640}}>
          <div className="hd">
            <span className="t">对话</span>
            <span className="mono">SSE · streaming</span>
            <span className="spacer" />
            <span className="tag">中文</span>
          </div>
          <div className="bd" style={{flex:1, display:'flex', flexDirection:'column', gap:2}}>
            <div className="chat-msg user">
              <div className="who">ops · 你</div>
              黄陂流域过去 3 小时雨量激增，S05 超警戒，帮我评估风险并生成应急预案。
            </div>
            <div className="chat-msg">
              <div className="who">supervisor</div>
              收到。已派发任务至 DataAnalyst / RiskAssessor / PlanGenerator 三个智能体并行处理。
            </div>
            <div className="chat-msg">
              <div className="who">dataanalyst</div>
              近 3h 累计雨量 86mm（S05 / S10 / S08），水位上涨速率 0.14 m/h，超过 80 分位阈值。
              <div className="ph-area" style={{height:80, marginTop:8}}>[ trend chart inline ]</div>
            </div>
            <div className="chat-msg">
              <div className="who">riskassessor</div>
              综合风险指数 <strong>62/100 · 中高</strong>。下游 3 个村镇处于 6h 潜在影响半径内。
            </div>
            <div className="chat-msg">
              <div className="who">plangenerator · streaming…</div>
              正在生成预案 PLAN-0419-A · 方案草稿：<br/>
              <span className="ph-line w80" style={{marginTop:6, display:'block'}}/>
              <span className="ph-line w60" style={{marginTop:4, display:'block'}}/>
              <span className="ph-line w40" style={{marginTop:4, display:'block'}}/>
            </div>
          </div>
          <div style={{padding:12, borderTop:'1.5px solid var(--line-soft)', display:'flex', gap:8}}>
            <div className="ph-area" style={{flex:1, height:40}}>[ 输入指令 / 自然语言 ]</div>
            <button className="btn primary">发送 ↵</button>
          </div>
        </div>

        {/* Timeline */}
        <div className="box">
          <div className="hd">
            <span className="t">智能体时间线</span>
            <span className="mono">6 agents · run #218</span>
          </div>
          <div className="bd">
            <div className="timeline">
              <div className="tl-item done">
                <div className="lbl">14:20:04 · 1.2s</div>
                <div className="t">Supervisor · 任务分派</div>
                <div style={{color:'var(--ink-soft)',fontSize:12,marginTop:2}}>拆分为 3 个并行子任务</div>
              </div>
              <div className="tl-item done">
                <div className="lbl">14:20:05 · 3.8s</div>
                <div className="t">DataAnalyst · 数据查询</div>
                <div style={{color:'var(--ink-soft)',fontSize:12,marginTop:2}}>拉取 12 站点 · 72h 时序</div>
              </div>
              <div className="tl-item done">
                <div className="lbl">14:20:09 · 2.1s</div>
                <div className="t">RiskAssessor · 风险评估</div>
                <div style={{color:'var(--ink-soft)',fontSize:12,marginTop:2}}>评分 62 / 100</div>
              </div>
              <div className="tl-item run">
                <div className="lbl">14:20:11 · running…</div>
                <div className="t">PlanGenerator · 预案生成</div>
                <div style={{height:4, background:'var(--line-soft)', borderRadius:2, marginTop:6, overflow:'hidden'}}>
                  <div style={{height:'100%', width:'66%', background:'var(--yellow)'}}/>
                </div>
              </div>
              <div className="tl-item">
                <div className="lbl">queued</div>
                <div className="t">ResourceDispatcher</div>
              </div>
              <div className="tl-item">
                <div className="lbl">queued</div>
                <div className="t">NotificationAgent</div>
              </div>
            </div>
          </div>
        </div>

        {/* Risk dashboard */}
        <div className="box">
          <div className="hd">
            <span className="t">风险看板</span>
            <span className="mono">realtime</span>
          </div>
          <div className="bd" style={{display:'grid',gap:14}}>
            <div style={{display:'flex',alignItems:'center',gap:10}}>
              <GaugePH value={62} label="RISK 62/100" />
              <div style={{flex:1,fontSize:12}}>
                <div style={{display:'flex',justifyContent:'space-between'}}><span>降雨风险</span><span className="mono">高</span></div>
                <div style={{height:5,background:'var(--line-soft)',marginTop:3,marginBottom:8}}>
                  <div style={{height:'100%',width:'78%',background:'#d88a8a'}}/>
                </div>
                <div style={{display:'flex',justifyContent:'space-between'}}><span>水位风险</span><span className="mono">中高</span></div>
                <div style={{height:5,background:'var(--line-soft)',marginTop:3,marginBottom:8}}>
                  <div style={{height:'100%',width:'62%',background:'var(--yellow)'}}/>
                </div>
                <div style={{display:'flex',justifyContent:'space-between'}}><span>下游暴露</span><span className="mono">中</span></div>
                <div style={{height:5,background:'var(--line-soft)',marginTop:3}}>
                  <div style={{height:'100%',width:'44%',background:'var(--blue)'}}/>
                </div>
              </div>
            </div>

            <div style={{borderTop:'1px solid var(--line-soft)', paddingTop:12}}>
              <div style={{fontFamily:'var(--font-mono)',fontSize:10.5,letterSpacing:'0.08em',color:'var(--ink-mute)',textTransform:'uppercase',marginBottom:8}}>
                生成中的预案 · draft
              </div>
              <div style={{border:'1px solid var(--line-soft)',borderRadius:4,padding:10}}>
                <div style={{display:'flex',justifyContent:'space-between'}}>
                  <strong>PLAN-0419-A</strong>
                  <span className="tag warn">draft</span>
                </div>
                <div style={{fontSize:12,color:'var(--ink-soft)',margin:'6px 0'}}>黄陂流域上游拦蓄 + 下游转移</div>
                <div style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)'}}>7 步 · 3 部门 · ETA 28 min</div>
              </div>
              <button className="btn" style={{marginTop:8, width:'100%', justifyContent:'center'}}>查看完整预案 →</button>
            </div>

            <div style={{borderTop:'1px solid var(--line-soft)', paddingTop:12}}>
              <div style={{fontFamily:'var(--font-mono)',fontSize:10.5,letterSpacing:'0.08em',color:'var(--ink-mute)',textTransform:'uppercase',marginBottom:8}}>
                受影响站点 · top 5
              </div>
              {['S05 · 黄陂上','S10 · 滠水口','S08 · 铁铺','S03 · 姚家集','S12 · 长堰'].map((s,i) => (
                <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'4px 0',fontSize:12,borderBottom: i<4?'1px dashed var(--line-soft)':'none'}}>
                  <span>{s}</span>
                  <span className="mono" style={{color:'var(--ink-mute)'}}>{[92,84,71,66,58][i]}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function AiCenterV2() {
  // Pipeline / flow centric
  return (
    <>
      <div className="wf-page-head">
        <h1>AI 命令中心</h1>
        <span className="sub">// variant 02 · agent pipeline flow</span>
        <span className="spacer" />
        <button className="btn">回放</button>
        <button className="btn primary">中止 run #218</button>
      </div>

      {/* Pipeline bar */}
      <div className="box" style={{marginBottom:14}}>
        <div className="hd">
          <span className="t">智能体流水线 · run #218</span>
          <span className="mono">2026-04-19 14:20:04 · elapsed 00:07.1</span>
          <span className="spacer" />
          <span className="tag blue">3/6 done</span>
          <span className="tag warn">1 running</span>
          <span className="tag">2 queued</span>
        </div>
        <div className="bd" style={{padding:0}}>
          <div className="pipeline">
            {AGENTS.map((a, i) => {
              const state = i < 3 ? 'done' : i === 3 ? 'run' : '';
              return (
                <div key={a.n} className={`agent-node ${state}`}>
                  <div className="n">AGENT {a.n}</div>
                  <div className="name">{a.name}</div>
                  <div style={{fontSize:11,color:'var(--ink-soft)'}}>{a.role}</div>
                  <div className="state">
                    {state==='done' && '✓ done · 2.1s'}
                    {state==='run' && '● running · 66%'}
                    {state==='' && '○ queued'}
                  </div>
                  {state === 'run' && (
                    <div style={{height:4, background:'var(--line-soft)', margin:'8px 6px 0', borderRadius:2, overflow:'hidden'}}>
                      <div style={{height:'100%', width:'66%', background:'var(--yellow)'}}/>
                    </div>
                  )}
                  <div className="arr" />
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <div className="grid" style={{gridTemplateColumns:'1fr 1.3fr', gap:14}}>
        {/* Chat column */}
        <div className="box" style={{display:'flex',flexDirection:'column',minHeight:560}}>
          <div className="hd">
            <span className="t">对话 / 输入</span>
            <span className="mono">prompt · natural language</span>
          </div>
          <div className="bd" style={{flex:1}}>
            <div className="chat-msg user">
              <div className="who">ops</div>
              S05 超警戒，生成应急预案并通知下游 3 个镇。
            </div>
            <div className="chat-msg">
              <div className="who">supervisor → routed</div>
              拆分任务 → Analyst / Risk / Plan / Dispatch / Notify
            </div>
            <div className="chat-msg">
              <div className="who">plangenerator · streaming</div>
              <span className="ph-line w80" style={{display:'block',marginBottom:4}}/>
              <span className="ph-line w60" style={{display:'block',marginBottom:4}}/>
              <span className="ph-line w40" style={{display:'block'}}/>
            </div>
          </div>
          <div style={{padding:12, borderTop:'1.5px solid var(--line-soft)', display:'flex', gap:8}}>
            <div className="ph-area" style={{flex:1, height:40}}>[ 输入指令 ]</div>
            <button className="btn primary">发送</button>
          </div>
        </div>

        {/* Agent detail + plan preview */}
        <div style={{display:'grid', gap:14}}>
          <div className="box">
            <div className="hd">
              <span className="t">PlanGenerator · 智能体详情</span>
              <span className="mono">running · 14:20:11 →</span>
              <span className="spacer" />
              <span className="tag warn">66%</span>
            </div>
            <div className="bd" style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:14}}>
              <div>
                <div style={{fontFamily:'var(--font-mono)',fontSize:10.5,color:'var(--ink-mute)',letterSpacing:'0.08em',textTransform:'uppercase',marginBottom:6}}>
                  Tool calls
                </div>
                {[
                  ['query_stations', 'done', '12 rows'],
                  ['get_thresholds', 'done', '4 rules'],
                  ['forecast_runoff', 'done', '6h model'],
                  ['compose_plan', 'running', '...'],
                ].map((t,i) => (
                  <div key={i} style={{display:'grid',gridTemplateColumns:'1fr auto auto',gap:8,padding:'6px 0',borderBottom:'1px dashed var(--line-soft)',fontFamily:'var(--font-mono)',fontSize:11}}>
                    <span>{t[0]}()</span>
                    <span className={`tag ${t[1]==='done'?'blue':'warn'}`}>{t[1]}</span>
                    <span style={{color:'var(--ink-mute)'}}>{t[2]}</span>
                  </div>
                ))}
              </div>
              <div>
                <div style={{fontFamily:'var(--font-mono)',fontSize:10.5,color:'var(--ink-mute)',letterSpacing:'0.08em',textTransform:'uppercase',marginBottom:6}}>
                  Token / Latency
                </div>
                <LineChartPH seeds={[3,9]} colors={['var(--blue)','#d88a8a']} height={100}/>
                <div style={{display:'flex',justifyContent:'space-between',fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)',marginTop:6}}>
                  <span>in 1,204 tok</span>
                  <span>out 389 tok</span>
                  <span>lat p50 820ms</span>
                </div>
              </div>
            </div>
          </div>

          <div className="box">
            <div className="hd">
              <span className="t">生成的应急预案 · 预览</span>
              <span className="mono">PLAN-0419-A · draft</span>
              <span className="spacer" />
              <button className="btn">编辑</button>
              <button className="btn primary">审批 → 执行</button>
            </div>
            <div className="bd" style={{display:'grid',gridTemplateColumns:'1.2fr 1fr',gap:14}}>
              <div>
                <div style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)'}}>步骤 · 7 steps</div>
                <ol style={{paddingLeft:18, margin:'8px 0', fontSize:12.5, lineHeight:1.7}}>
                  <li>上游水库预泄 · <span className="mono" style={{color:'var(--ink-mute)'}}>10 min</span></li>
                  <li>S05 / S10 断面加固 · <span className="mono" style={{color:'var(--ink-mute)'}}>30 min</span></li>
                  <li>下游 3 镇预警广播 · <span className="mono" style={{color:'var(--ink-mute)'}}>5 min</span></li>
                  <li>低洼区域人员转移 · <span className="mono" style={{color:'var(--ink-mute)'}}>60 min</span></li>
                  <li>抢险队伍集结（A/B/C）</li>
                  <li>泵车调度 · 8 辆</li>
                  <li>持续监测与复盘</li>
                </ol>
              </div>
              <div>
                <div style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)',marginBottom:6}}>资源 / 部门</div>
                <div className="grid g-2" style={{gap:8}}>
                  {[
                    ['水利局','lead'],
                    ['应急办','co'],
                    ['气象','data'],
                    ['交通','support'],
                    ['抢险队×3','exec'],
                    ['泵车 8','exec'],
                  ].map((r,i) => (
                    <div key={i} style={{border:'1px solid var(--line-soft)',padding:'6px 8px',borderRadius:3,fontSize:12,display:'flex',justifyContent:'space-between'}}>
                      <span>{r[0]}</span>
                      <span className="mono" style={{color:'var(--ink-mute)'}}>{r[1]}</span>
                    </div>
                  ))}
                </div>
                <div style={{marginTop:10, fontSize:12, color:'var(--ink-soft)'}}>
                  预计完成 <strong>28 min</strong> · 影响 <strong>3 镇 / 12k 人</strong>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { AiCenterV1, AiCenterV2 });
