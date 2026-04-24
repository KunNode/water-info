// Login page wireframe

function LoginPage() {
  return (
    <div style={{minHeight:'100vh',display:'grid',gridTemplateColumns:'1.1fr 1fr',background:'var(--paper)'}}>
      {/* Left brand panel */}
      <div style={{background:'var(--paper-2)',borderRight:'1.5px solid var(--line)',padding:'48px 56px',display:'flex',flexDirection:'column',justifyContent:'space-between'}}>
        <div className="wf-brand" style={{fontSize:18}}>
          <span className="logo" style={{width:34,height:34,fontSize:16}}>水</span>
          <span>防洪应急 · 多智能体平台</span>
        </div>
        <div>
          <div style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)',letterSpacing:'0.12em',textTransform:'uppercase',marginBottom:12}}>
            v1.0 · 水务指挥中心
          </div>
          <h1 style={{fontSize:36,lineHeight:1.2,margin:0,fontWeight:600,maxWidth:500}}>
            AI 驱动的<br/>防洪应急决策支持
          </h1>
          <p style={{fontSize:13,color:'var(--ink-soft)',maxWidth:420,marginTop:20,lineHeight:1.6}}>
            132 个水文站实时接入 · 6 个智能体协同决策 · 从监测到预案生成 · 4 分钟内完成
          </p>

          <div className="ph-area" style={{marginTop:32,width:480,height:240}}>
            [ 流域插图 / 品牌视觉占位 ]
          </div>
        </div>
        <div style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)'}}>
          © 2026 · build 20260419
        </div>
      </div>

      {/* Right form */}
      <div style={{display:'grid',placeItems:'center',padding:48}}>
        <div className="box" style={{width:400,padding:36}}>
          <h2 style={{fontSize:22,margin:0,fontWeight:600}}>登录</h2>
          <div style={{fontSize:12,color:'var(--ink-mute)',marginTop:4,fontFamily:'var(--font-mono)'}}>
            JWT · ADMIN / OPERATOR / VIEWER
          </div>

          <div style={{marginTop:24}}>
            <FormRow label="用户名"><Input placeholder="admin@ops" /></FormRow>
            <FormRow label="密码"><Input placeholder="••••••••" /></FormRow>
            <FormRow label="验证码">
              <div style={{display:'flex',gap:8}}>
                <Input value="6 2 7 4" w={140}/>
                <div className="ph-area" style={{width:100,height:32,fontSize:10}}>CAPTCHA</div>
              </div>
            </FormRow>
          </div>

          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginTop:14,fontSize:12}}>
            <label style={{display:'inline-flex',alignItems:'center',gap:6}}>
              <input type="checkbox" defaultChecked /> 记住密码
            </label>
            <a href="#" style={{color:'var(--blue)'}}>忘记密码?</a>
          </div>

          <button className="btn primary" style={{width:'100%',justifyContent:'center',marginTop:20,padding:'10px 0'}}>
            登录 →
          </button>

          <div style={{marginTop:18,fontSize:11,color:'var(--ink-mute)',fontFamily:'var(--font-mono)',textAlign:'center'}}>
            demo / admin · demo / operator · demo / viewer
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { LoginPage });
