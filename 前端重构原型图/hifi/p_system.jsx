// System: User, Role, OrgDept, Log + Login

function UserPage() {
  const rows = [
    ['admin','王建国','系统管理员','指挥中心','13800001234','online','14:22','-'],
    ['ops01','李小明','值班员','运维部','13800001122','online','14:20','-'],
    ['ops02','张伟','值班员','运维部','13800002233','offline','13:45','-'],
    ['view01','陈晓','只读','气象局','13800003344','online','14:18','-'],
    ['view02','赵敏','只读','水利局','13800004455','offline','昨日','-'],
    ['plan01','刘飞','预案编制','应急办','13800005566','online','14:15','-'],
  ];
  return (
    <>
      <div className="page-head">
        <h1>用户管理</h1>
        <span className="sub">// 42 users · 6 roles</span>
        <span className="sp"/>
        <button className="btn">批量导入</button>
        <button className="btn primary">{I.plus}新建用户</button>
      </div>
      <div className="toolbar">
        <div className="input" style={{width:280}}><span className="ico">{I.search}</span><input placeholder="账号 / 姓名 / 手机号"/></div>
        <span className="tag info">全部角色</span>
        <span className="tag">全部部门</span>
        <span className="sp" style={{flex:1}}/>
      </div>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>账号</th><th>姓名</th><th>角色</th><th>部门</th><th>手机</th><th>在线</th><th>最近登录</th><th></th></tr></thead>
          <tbody>{rows.map((r,i)=>(
            <tr key={i}>
              <td><div style={{display:'flex',alignItems:'center',gap:10}}>
                <div style={{width:28,height:28,borderRadius:'50%',background:'linear-gradient(135deg,var(--brand),var(--brand-2))',display:'grid',placeItems:'center',color:'#03132b',fontSize:12,fontWeight:700}}>{r[1][0]}</div>
                <span className="mono">{r[0]}</span>
              </div></td>
              <td style={{fontWeight:500}}>{r[1]}</td>
              <td><span className="tag info">{r[2]}</span></td>
              <td className="soft">{r[3]}</td>
              <td className="mono muted" style={{fontSize:11.5}}>{r[4]}</td>
              <td><span className={`tag ${r[5]==='online'?'info':''}`}><span className={`dot ${r[5]==='online'?'ok':''}`}/>{r[5]==='online'?'在线':'离线'}</span></td>
              <td className="mono muted" style={{fontSize:11}}>{r[6]}</td>
              <td style={{textAlign:'right'}}><button className="btn sm ghost">编辑 {I.chevR}</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}

function RolePage() {
  const roles = [
    ['ADMIN','系统管理员','3',['系统设置','用户管理','角色管理','全部数据','预案执行']],
    ['COMMANDER','指挥长','2',['全部数据','预案审批','预案执行','告警处置']],
    ['OPERATOR','值班员','8',['站点查看','告警处置','数据查询']],
    ['PLANNER','预案编制','4',['预案库','预案编辑','数据查询']],
    ['VIEWER','只读','12',['数据查询','大屏查看']],
  ];
  return (
    <>
      <div className="page-head">
        <h1>角色 & 权限</h1>
        <span className="sub">// RBAC · 5 roles · 24 permissions</span>
        <span className="sp"/>
        <button className="btn primary">{I.plus}新建角色</button>
      </div>
      <div className="grid g-12">
        <div className="card" style={{gridColumn:'span 4'}}>
          <div className="card-head"><span className="title">角色列表</span></div>
          <div style={{display:'grid'}}>
            {roles.map((r,i)=>(
              <div key={i} style={{padding:16,borderBottom:'1px solid var(--line)',background:i===0?'rgba(73,225,255,0.06)':'transparent',borderLeft:i===0?'3px solid var(--brand-2)':'3px solid transparent',cursor:'pointer'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                  <span className="mono brand" style={{color:'var(--brand-2)',fontSize:11,letterSpacing:'0.1em'}}>{r[0]}</span>
                  <span className="tag">{r[2]} 人</span>
                </div>
                <div style={{fontWeight:600,marginTop:6}}>{r[1]}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="card" style={{gridColumn:'span 8'}}>
          <div className="card-head"><span className="title">ADMIN · 权限清单</span><span className="mono">24 / 24 已分配</span></div>
          <div className="card-body">
            {[['系统',['系统设置','用户管理','角色管理','组织管理','日志查看']],['监测',['站点查看','站点编辑','传感器管理','数据订阅']],['告警',['告警查看','告警处置','阈值配置','通知渠道']],['AI 预案',['AI 对话','预案生成','预案审批','预案执行','预案归档']],['数据',['历史查询','原始数据导出','实时 API']]].map((g,i)=>(
              <div key={i} style={{padding:'14px 0',borderBottom: i<4?'1px solid var(--line)':''}}>
                <div className="label-small" style={{marginBottom:8}}>{g[0]}</div>
                <div style={{display:'flex',flexWrap:'wrap',gap:8}}>
                  {g[1].map((p,j)=>(
                    <label key={j} style={{display:'flex',alignItems:'center',gap:8,padding:'6px 12px',border:'1px solid var(--line)',borderRadius:6,fontSize:12.5,background:'var(--bg-2)',cursor:'pointer'}}>
                      <span className="switch on" style={{width:24,height:14}}/>
                      <span>{p}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

function OrgDeptPage() {
  return (
    <>
      <div className="page-head">
        <h1>组织部门</h1>
        <span className="sub">// 7 dept · 42 users</span>
        <span className="sp"/>
        <button className="btn primary">{I.plus}新建部门</button>
      </div>
      <div className="grid g-12">
        <div className="card" style={{gridColumn:'span 5'}}>
          <div className="card-head"><span className="title">组织架构</span></div>
          <div className="card-body" style={{fontSize:13}}>
            {[
              ['▼ 武汉市水务应急指挥中心','42 人',0,true],
              ['▼ 指挥中心','5 人',1,true],
              ['· 领导组','2 人',2],
              ['· 值班室','3 人',2],
              ['▼ 运维部','12 人',1,true],
              ['· 监测运维组','6 人',2],
              ['· 设备组','6 人',2],
              ['▼ 预案组','6 人',1],
              ['▼ 气象联络','4 人',1],
              ['▼ 水利协同','8 人',1],
              ['▼ 应急办','4 人',1],
              ['· 只读账号池','3 人',1],
            ].map((r,i)=>(
              <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'8px 0',paddingLeft:r[2]*20,borderBottom:'1px dashed var(--line)',fontWeight:r[3]?600:400,color:r[3]?'var(--fg)':'var(--fg-soft)'}}>
                <span>{r[0]}</span>
                <span className="mono muted" style={{fontSize:11}}>{r[1]}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card" style={{gridColumn:'span 7'}}>
          <div className="card-head"><span className="title">运维部 · 详情</span></div>
          <div className="card-body">
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:16}}>
              <div><span className="label-small">部门负责人</span><div style={{fontWeight:500,marginTop:4}}>李小明</div></div>
              <div><span className="label-small">部门编码</span><div className="mono" style={{marginTop:4}}>DEP-OPS-001</div></div>
              <div><span className="label-small">人数</span><div style={{fontWeight:500,marginTop:4}}>12 (9 在线)</div></div>
              <div><span className="label-small">默认角色</span><div style={{marginTop:4}}><span className="tag info">OPERATOR</span></div></div>
            </div>
            <div className="divider"/>
            <div className="label-small" style={{margin:'16px 0 10px'}}>成员</div>
            <div style={{display:'grid',gridTemplateColumns:'repeat(4, 1fr)',gap:10}}>
              {['李小明','张伟','王志','陈宇','刘芳','赵强','周伟','吴鹏','郑海','孙明','马涛','朱琳'].map((n,i)=>(
                <div key={i} style={{display:'flex',alignItems:'center',gap:8,padding:'8px 10px',border:'1px solid var(--line)',borderRadius:6,background:'var(--bg-2)'}}>
                  <div style={{width:24,height:24,borderRadius:'50%',background:'linear-gradient(135deg,var(--brand),var(--brand-2))',display:'grid',placeItems:'center',color:'#03132b',fontSize:11,fontWeight:700}}>{n[0]}</div>
                  <span style={{fontSize:12.5}}>{n}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function LogPage() {
  const rows = [
    ['2026-04-19 14:22:08','admin','告警处置','确认告警 ALM-24190418','10.0.12.5','success'],
    ['2026-04-19 14:20:45','admin','预案执行','推进步骤 3/7 · PLAN-0419-A','10.0.12.5','success'],
    ['2026-04-19 14:18:02','system','告警','自动触发 · S05 超警戒','—','success'],
    ['2026-04-19 14:15:33','ops01','数据查询','导出 S10 观测数据 24h','10.0.12.18','success'],
    ['2026-04-19 14:05:22','admin','预案执行','启动 PLAN-0419-A · Ⅳ 级响应','10.0.12.5','success'],
    ['2026-04-19 14:02:11','ops02','用户','尝试修改权限 (越权)','10.0.12.19','denied'],
    ['2026-04-19 13:58:44','plan01','预案','保存草稿 PLAN-DRAFT-0087','10.0.12.22','success'],
    ['2026-04-19 13:50:01','admin','系统','修改通知渠道 · 短信网关','10.0.12.5','success'],
    ['2026-04-19 13:45:12','view01','登录','登录成功','10.0.12.33','success'],
    ['2026-04-19 13:44:58','view01','登录','密码错误 · 第 1 次','10.0.12.33','fail'],
  ];
  return (
    <>
      <div className="page-head">
        <h1>操作日志</h1>
        <span className="sub">// 审计 · 24h 共 218 条</span>
        <span className="sp"/>
        <button className="btn">{I.download}导出</button>
        <button className="btn">{I.filter}筛选</button>
      </div>
      <div className="toolbar">
        <div className="input" style={{width:280}}><span className="ico">{I.search}</span><input placeholder="账号 / 模块 / 描述"/></div>
        <span className="tag info">全部模块</span>
        <span className="tag">全部结果</span>
        <span className="tag">近 24 小时</span>
        <span className="sp" style={{flex:1}}/>
      </div>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>时间</th><th>账号</th><th>模块</th><th>操作</th><th>IP</th><th>结果</th></tr></thead>
          <tbody>{rows.map((r,i)=>(
            <tr key={i}>
              <td className="mono muted" style={{fontSize:11.5}}>{r[0]}</td>
              <td className="mono">{r[1]}</td>
              <td><span className="tag">{r[2]}</span></td>
              <td>{r[3]}</td>
              <td className="mono muted" style={{fontSize:11}}>{r[4]}</td>
              <td><span className={`tag ${r[5]==='success'?'info':r[5]==='denied'?'warn':'danger'}`}>{r[5]==='success'?'成功':r[5]==='denied'?'拒绝':'失败'}</span></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}

function LoginPage({ onEnter }) {
  return (
    <div style={{position:'fixed',inset:0,background:'var(--bg)',display:'grid',gridTemplateColumns:'1.3fr 1fr',overflow:'hidden'}}>
      <div style={{position:'relative',overflow:'hidden',background:'radial-gradient(800px 600px at 30% 40%, rgba(62,166,255,0.25), transparent 60%), radial-gradient(600px 500px at 70% 70%, rgba(73,225,255,0.18), transparent 60%), linear-gradient(180deg, #05101f 0%, #030812 100%)'}}>
        <svg width="100%" height="100%" style={{position:'absolute',inset:0}}>
          <defs>
            <pattern id="grid-login" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M60 0H0V60" fill="none" stroke="rgba(73,225,255,0.08)" strokeWidth="0.5"/>
            </pattern>
            <linearGradient id="wave-login" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#49e1ff" stopOpacity="0.6"/>
              <stop offset="100%" stopColor="#49e1ff" stopOpacity="0"/>
            </linearGradient>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid-login)"/>
          {[0,1,2,3,4].map(i => (
            <path key={i} d={`M0 ${200+i*80} Q 200 ${150+i*80} 400 ${220+i*80} T 800 ${180+i*80} T 1200 ${220+i*80}`} fill="none" stroke="url(#wave-login)" strokeWidth="1.5"/>
          ))}
          {/* Drifting particles */}
          {Array.from({length:20}).map((_,i)=>(
            <circle key={i} cx={50+i*60} cy={100+Math.sin(i)*200+i*20} r={1.5} fill="#49e1ff" opacity="0.6">
              <animate attributeName="cy" values={`${100+i*30};${600+i*30};${100+i*30}`} dur={`${8+i%5}s`} repeatCount="indefinite"/>
              <animate attributeName="opacity" values="0;0.8;0" dur={`${8+i%5}s`} repeatCount="indefinite"/>
            </circle>
          ))}
        </svg>
        <div style={{position:'relative',padding:'56px 64px',display:'flex',flexDirection:'column',height:'100%',justifyContent:'space-between'}}>
          <div style={{display:'flex',alignItems:'center',gap:14}}>
            <div className="brand-mark" style={{width:44,height:44,fontSize:20}}>F</div>
            <div>
              <div style={{fontSize:18,fontWeight:700,color:'var(--fg)'}}>FloodMind</div>
              <div className="mono muted" style={{fontSize:11,letterSpacing:'0.15em'}}>HYDRO · INTELLIGENCE · PLATFORM</div>
            </div>
          </div>
          <div>
            <div style={{fontSize:46,fontWeight:700,lineHeight:1.15,color:'var(--fg)',maxWidth:600}}>
              让水 <span style={{background:'linear-gradient(90deg,var(--brand-2),var(--brand))',WebkitBackgroundClip:'text',backgroundClip:'text',color:'transparent'}}>被预见</span>。<br/>让决策 <span style={{background:'linear-gradient(90deg,var(--brand-2),var(--brand))',WebkitBackgroundClip:'text',backgroundClip:'text',color:'transparent'}}>有 AI 托底</span>。
            </div>
            <div style={{color:'var(--fg-soft)',marginTop:20,maxWidth:520,lineHeight:1.7,fontSize:14}}>
              六个智能体协同作业，从监测到预案生成，4 分钟内完成一次完整的防洪应急决策闭环。
            </div>
            <div style={{display:'flex',gap:24,marginTop:32}}>
              {[['132','接入站点'],['617','传感设备'],['6','智能体'],['4 min','端到端']].map((k,i)=>(
                <div key={i}>
                  <div className="mono" style={{fontSize:28,fontWeight:700,background:'linear-gradient(90deg,var(--brand-2),var(--brand))',WebkitBackgroundClip:'text',backgroundClip:'text',color:'transparent'}}>{k[0]}</div>
                  <div className="muted" style={{fontSize:11,letterSpacing:'0.1em',marginTop:2}}>{k[1]}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="mono muted" style={{fontSize:11,letterSpacing:'0.15em'}}>© 2026 FLOODMIND · WUHAN HYDRO OPS · v1.0.0</div>
        </div>
      </div>
      <div style={{display:'grid',placeItems:'center',padding:40}}>
        <div style={{width:'100%',maxWidth:420}}>
          <div style={{fontSize:26,fontWeight:700}}>登录</div>
          <div className="muted" style={{marginTop:6,fontSize:13}}>使用工号或授权账号进入指挥中心</div>

          <div style={{marginTop:32,display:'grid',gap:16}}>
            <div>
              <span className="label-small">账号</span>
              <div className="input" style={{padding:'10px 14px',marginTop:6}}>
                <input defaultValue="admin" style={{fontSize:14}}/>
              </div>
            </div>
            <div>
              <span className="label-small">密码</span>
              <div className="input" style={{padding:'10px 14px',marginTop:6}}>
                <input type="password" defaultValue="********" style={{fontSize:14}}/>
              </div>
            </div>
            <div>
              <span className="label-small">验证码</span>
              <div style={{display:'flex',gap:10,marginTop:6}}>
                <div className="input" style={{flex:1,padding:'10px 14px'}}><input defaultValue="A8X2" style={{fontSize:14}}/></div>
                <div style={{width:110,height:42,background:'linear-gradient(135deg,#0a1628,#06121f)',border:'1px solid var(--line)',borderRadius:8,display:'grid',placeItems:'center',fontFamily:'var(--font-mono)',fontSize:18,letterSpacing:'0.2em',color:'var(--brand-2)',fontWeight:700,textDecoration:'line-through',textDecorationColor:'rgba(73,225,255,0.3)'}}>A8X2</div>
              </div>
            </div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',fontSize:12.5}}>
              <label style={{display:'flex',alignItems:'center',gap:8,cursor:'pointer'}}>
                <span className="switch on" style={{width:28,height:16}}/>
                <span className="soft">记住密码</span>
              </label>
              <a className="brand" style={{color:'var(--brand-2)'}} href="#">忘记密码?</a>
            </div>
            <button className="btn primary" style={{marginTop:8,padding:'12px 20px',justifyContent:'center',fontSize:14}} onClick={onEnter}>
              进入指挥中心 {I.chevR}
            </button>
            <div className="muted" style={{textAlign:'center',fontSize:11,marginTop:8}}>
              登录即表示同意 <a className="brand" style={{color:'var(--brand-2)'}}>《数据安全承诺》</a> · 启用双因子
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { UserPage, RolePage, OrgDeptPage, LogPage, LoginPage });
