// BigScreen — 1920x1080 hi-fi command screen

function BSHeader() {
  return (
    <div style={{display:'flex',alignItems:'center',gap:18,position:'relative',zIndex:2}}>
      {/* corner decoration */}
      <div style={{position:'absolute',left:-16,top:-10,width:40,height:40,borderLeft:'2px solid #49e1ff',borderTop:'2px solid #49e1ff',boxShadow:'0 0 12px rgba(73,225,255,0.5)'}}/>
      <div style={{position:'absolute',right:-16,top:-10,width:40,height:40,borderRight:'2px solid #49e1ff',borderTop:'2px solid #49e1ff',boxShadow:'0 0 12px rgba(73,225,255,0.5)'}}/>

      <div style={{width:44,height:44,borderRadius:10,background:'var(--grad-brand)',display:'grid',placeItems:'center',fontWeight:700,color:'#fff',fontSize:22,boxShadow:'0 0 24px rgba(73,225,255,0.6)'}}>F</div>
      <div style={{flex:1,textAlign:'center'}}>
        <div style={{fontSize:34,fontWeight:700,letterSpacing:'0.2em',background:'linear-gradient(90deg,#9aefff,#ffffff,#9aefff)',WebkitBackgroundClip:'text',WebkitTextFillColor:'transparent'}}>FloodMind · 流域防洪应急指挥中心</div>
        <div style={{fontSize:11,fontFamily:'var(--font-mono)',color:'var(--fg-mute)',letterSpacing:'0.3em',marginTop:2}}>WATERSHED · FLOOD · AI COMMAND · V1.0</div>
      </div>
      <div style={{display:'flex',gap:10,alignItems:'center'}}>
        <span className="chip"><span className="ind"/>LIVE</span>
        <span className="chip">2026-04-19 14:22:08</span>
      </div>
    </div>
  );
}

function BSPanel({ title, mono, children, style }) {
  return (
    <div style={{
      background:'linear-gradient(180deg, rgba(17,30,60,0.5), rgba(11,18,32,0.4))',
      border:'1px solid rgba(73,225,255,0.25)',
      borderRadius:4,
      boxShadow:'0 0 0 1px rgba(73,225,255,0.05) inset, 0 20px 60px -30px rgba(47,123,255,0.3)',
      backdropFilter:'blur(10px)',
      position:'relative',
      ...style
    }}>
      {/* corner bits */}
      <div style={{position:'absolute',left:-1,top:-1,width:14,height:14,borderLeft:'2px solid #49e1ff',borderTop:'2px solid #49e1ff'}}/>
      <div style={{position:'absolute',right:-1,top:-1,width:14,height:14,borderRight:'2px solid #49e1ff',borderTop:'2px solid #49e1ff'}}/>
      <div style={{position:'absolute',left:-1,bottom:-1,width:14,height:14,borderLeft:'2px solid #49e1ff',borderBottom:'2px solid #49e1ff'}}/>
      <div style={{position:'absolute',right:-1,bottom:-1,width:14,height:14,borderRight:'2px solid #49e1ff',borderBottom:'2px solid #49e1ff'}}/>
      <div style={{padding:'10px 14px',borderBottom:'1px solid rgba(73,225,255,0.2)',display:'flex',alignItems:'center',gap:10}}>
        <span style={{width:3,height:14,background:'#49e1ff',boxShadow:'0 0 8px #49e1ff'}}/>
        <span style={{fontSize:15,fontWeight:600,letterSpacing:'0.1em'}}>{title}</span>
        <span style={{marginLeft:'auto',fontFamily:'var(--font-mono)',fontSize:10,color:'rgba(154,239,255,0.6)',letterSpacing:'0.15em'}}>{mono}</span>
      </div>
      <div style={{padding:12,height:'calc(100% - 38px)'}}>{children}</div>
    </div>
  );
}

function BSStat({ label, value, unit, color = '#49e1ff' }) {
  return (
    <div style={{padding:'12px 14px',textAlign:'center',borderRight:'1px solid rgba(73,225,255,0.15)'}}>
      <div style={{fontSize:11,color:'rgba(154,239,255,0.6)',fontFamily:'var(--font-mono)',letterSpacing:'0.18em'}}>{label}</div>
      <div style={{fontSize:34,fontWeight:700,marginTop:4,color,textShadow:`0 0 12px ${color}`,fontVariantNumeric:'tabular-nums'}}>
        {value}<span style={{fontSize:14,color:'rgba(255,255,255,0.5)',marginLeft:4}}>{unit}</span>
      </div>
    </div>
  );
}

function BigScreen() {
  return (
    <div className="bs-root">
      <BSHeader/>
      <div style={{display:'grid',gridTemplateColumns:'380px 1fr 380px',gap:18,minHeight:0}}>
        {/* LEFT */}
        <div style={{display:'grid',gridTemplateRows:'auto 1fr 1fr',gap:18,minHeight:0}}>
          <BSPanel title="核心指标" mono="KPI · LIVE">
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:0}}>
              <BSStat label="ONLINE" value="128" unit="/132"/>
              <BSStat label="ALERTS" value="17" unit="" color="#ff5a6a"/>
              <BSStat label="MAX RAIN" value="86" unit="mm"/>
              <BSStat label="RISK" value="62" unit="/100" color="#ffb547"/>
            </div>
          </BSPanel>
          <BSPanel title="24H 区域雨量" mono="mm · hour">
            <GlowBars bars={24} height={160} color="#2f7bff"/>
            <div style={{marginTop:8,display:'flex',justifyContent:'space-between',fontFamily:'var(--font-mono)',fontSize:10,color:'rgba(154,239,255,0.5)'}}>
              <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>24:00</span>
            </div>
          </BSPanel>
          <BSPanel title="流域风险评估" mono="AI · realtime">
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <RadialGauge value={62} size={150}/>
              <div style={{flex:1,fontSize:12}}>
                {[['降雨',78,'#ff5a6a'],['水位',62,'#ffb547'],['暴露',44,'#49e1ff']].map((r,i)=>(
                  <div key={i} style={{marginBottom:10}}>
                    <div style={{display:'flex',justifyContent:'space-between',marginBottom:4,color:'rgba(255,255,255,0.7)'}}>
                      <span>{r[0]}</span><span style={{fontFamily:'var(--font-mono)'}}>{r[1]}%</span>
                    </div>
                    <div className="progress" style={{background:'rgba(73,225,255,0.08)'}}>
                      <div className="bar" style={{width:`${r[1]}%`,background:r[2],boxShadow:`0 0 8px ${r[2]}`}}/>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </BSPanel>
        </div>

        {/* CENTER — BIG MAP */}
        <BSPanel title="流域态势 · 滠水流域" mono="GIS · 132 STATIONS">
          <div style={{position:'relative',height:'100%'}}>
            <FlowMap height={800}/>
            <RainDrops count={30}/>
            {/* floating title badges */}
            <div style={{position:'absolute',left:12,top:12,fontFamily:'var(--font-mono)',fontSize:10,color:'rgba(154,239,255,0.6)',letterSpacing:'0.15em',lineHeight:1.8}}>
              <div>LAT  30.8742° N</div>
              <div>LON 114.3758° E</div>
              <div>ALT     47 m</div>
            </div>
            <div style={{position:'absolute',right:12,top:12,background:'rgba(11,18,32,0.8)',padding:'8px 12px',border:'1px solid rgba(255,90,106,0.4)',borderRadius:4}}>
              <div style={{fontFamily:'var(--font-mono)',fontSize:10,color:'#ff8a96',letterSpacing:'0.15em'}}>⚠ ACTIVE ALERT</div>
              <div style={{fontSize:16,fontWeight:600,color:'#ff5a6a',marginTop:4}}>S05 超警戒水位</div>
              <div style={{fontSize:11,color:'rgba(255,255,255,0.7)',marginTop:2}}>+0.42m · 持续上涨 6h</div>
            </div>
          </div>
        </BSPanel>

        {/* RIGHT */}
        <div style={{display:'grid',gridTemplateRows:'1fr 1fr 1fr',gap:18,minHeight:0}}>
          <BSPanel title="实时告警流" mono="17 OPEN">
            <div style={{display:'flex',flexDirection:'column',gap:6,height:'100%',overflow:'hidden'}}>
              {[['14:18','S05','超警戒 +0.42m','crit'],['14:11','S10','1h雨量38mm','crit'],['13:54','S03','传感器离线','warn'],['13:32','S08','流速异常','warn'],['13:05','S05','持续上涨 6h','warn']].map((r,i)=>(
                <div key={i} style={{display:'grid',gridTemplateColumns:'44px 40px 1fr auto',gap:8,fontSize:11,padding:'6px 8px',background:'rgba(73,225,255,0.04)',borderLeft:`2px solid ${r[3]==='crit'?'#ff5a6a':'#ffb547'}`,alignItems:'center'}}>
                  <span style={{fontFamily:'var(--font-mono)',color:'rgba(154,239,255,0.6)'}}>{r[0]}</span>
                  <span style={{fontFamily:'var(--font-mono)',color:'#9aefff'}}>{r[1]}</span>
                  <span style={{color:'rgba(255,255,255,0.85)'}}>{r[2]}</span>
                  <span style={{fontFamily:'var(--font-mono)',fontSize:9,color:r[3]==='crit'?'#ff8a96':'#ffc96e',padding:'1px 5px',border:`1px solid ${r[3]==='crit'?'#ff5a6a':'#ffb547'}`}}>{r[3].toUpperCase()}</span>
                </div>
              ))}
            </div>
          </BSPanel>
          <BSPanel title="关键站点水位" mono="S05 · S10 · S08">
            <GlowLine seeds={[1,2,3]} colors={['#49e1ff','#ff5a6a','#ffb547']} height={180} animate/>
          </BSPanel>
          <BSPanel title="耗水量 · 12M" mono="3D · million m³">
            <Water3D height={200}/>
          </BSPanel>
        </div>
      </div>
    </div>
  );
}

function BigScreenPage() {
  const wrapRef = React.useRef(null);
  const [scale, setScale] = React.useState(1);
  React.useEffect(() => {
    const update = () => {
      if (!wrapRef.current) return;
      const w = wrapRef.current.clientWidth - 24;
      const h = Math.max(window.innerHeight - 180, 500);
      setScale(Math.min(w / 1920, h / 1080));
    };
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);
  return (
    <>
      <div className="page-head">
        <h1>指挥大屏</h1>
        <span className="sub">// 1920×1080 · scaled preview</span>
        <span className="sp"/>
        <button className="btn">{I.settings}布局</button>
        <button className="btn primary">全屏投放</button>
      </div>
      <div ref={wrapRef} className="bs-stage" style={{height: Math.max(540, 1080*scale + 24)}}>
        <div style={{position:'relative',width:1920*scale,height:1080*scale,margin:'0 auto'}}>
          <div className="bs-scaler" style={{transform:`scale(${scale})`}}>
            <BigScreen/>
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { BigScreenPage });
