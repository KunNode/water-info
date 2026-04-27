// Station, Sensor, Observation, Map pages

function StationPage() {
  const rows = [
    ['S05','黄陂站','水位+雨量+流速','滠水流域','online','28.92','+0.42','14:22:01','主动','李工'],
    ['S10','前川站','水位+雨量','滠水流域','online','27.41','+0.18','14:21:58','主动','王工'],
    ['S03','祁家湾','水位+雨量','府河流域','offline','—','—','14:08:32','备用','赵工'],
    ['S08','木兰站','流速+水温','木兰湖','online','2.14','-0.05','14:22:03','主动','李工'],
    ['S12','盘龙城','水位+流速','府河流域','online','24.18','+0.09','14:21:55','主动','张工'],
    ['S07','长轩岭','水位+雨量','倒水流域','online','22.03','+0.02','14:22:00','主动','王工'],
    ['S14','六指街','雨量','黄陂北部','warn','—','—','14:20:12','备用','赵工'],
    ['S02','前川桥','水位','滠水流域','online','26.88','+0.12','14:21:49','主动','张工'],
  ];
  return (
    <>
      <div className="page-head">
        <h1>站点管理</h1>
        <span className="sub">// 132 总 · 128 在线 · 4 异常</span>
        <span className="sp"/>
        <button className="btn">{I.download}导出</button>
        <button className="btn">{I.filter}筛选</button>
        <button className="btn primary">{I.plus}新建站点</button>
      </div>
      <div className="grid g-4" style={{marginBottom:16}}>
        <KPICard label="站点总数" value="132" delta="+3 · 本月" color="#49e1ff" seed={2}/>
        <KPICard label="在线" value="128" delta="97.0%" color="#2bd99f" seed={3}/>
        <KPICard label="异常" value="4" delta="其中 1 离线" color="#ffb547" seed={5}/>
        <KPICard label="流域覆盖" value="8" delta="滠水 · 府河 · 倒水..." color="#49e1ff" seed={7}/>
      </div>
      <div className="toolbar">
        <div className="input" style={{width:280}}><span className="ico">{I.search}</span><input placeholder="站点编号 / 名称 / 流域"/></div>
        <span className="tag info">全部流域</span>
        <span className="tag">全部类型</span>
        <span className="tag">在线状态</span>
        <span className="sp" style={{flex:1}}/>
        <span className="mono muted" style={{fontSize:11}}>共 132 · 显示 1–20</span>
      </div>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>编号</th><th>名称</th><th>类型</th><th>流域</th><th>状态</th><th>实时值</th><th>变化</th><th>最后上报</th><th>负责人</th><th></th></tr></thead>
          <tbody>{rows.map((r,i)=>(
            <tr key={i}>
              <td className="mono brand" style={{color:'var(--brand-2)'}}>{r[0]}</td>
              <td style={{fontWeight:500}}>{r[1]}</td>
              <td className="soft">{r[2]}</td>
              <td className="soft">{r[3]}</td>
              <td>
                <span className={`tag ${r[4]==='online'?'info':r[4]==='warn'?'warn':'danger'}`}>
                  <span className={`dot ${r[4]==='online'?'ok':r[4]==='warn'?'warn':'danger'}`}/>
                  {r[4]==='online'?'在线':r[4]==='warn'?'异常':'离线'}
                </span>
              </td>
              <td className="mono" style={{fontWeight:600}}>{r[5]}</td>
              <td className={`mono ${r[6].startsWith('+')?'':'soft'}`} style={{color:r[6].startsWith('+')?'#ffb547':'var(--fg-mute)'}}>{r[6]}</td>
              <td className="mono muted" style={{fontSize:11}}>{r[7]}</td>
              <td className="soft">{r[9]}</td>
              <td style={{textAlign:'right'}}><button className="btn sm ghost">详情 {I.chevR}</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}

function SensorPage() {
  const rows = [
    ['SNR-1001','S05','水位 Z','HydroPro-300','±1 cm','98.2%','online'],
    ['SNR-1002','S05','雨量 P','RainLog-II','±0.2 mm','99.1%','online'],
    ['SNR-1003','S05','流速 V','Sontek-M9','±0.5%','96.4%','online'],
    ['SNR-2001','S10','水位 Z','HydroPro-300','±1 cm','97.8%','online'],
    ['SNR-2002','S10','雨量 P','RainLog-II','±0.2 mm','99.4%','online'],
    ['SNR-3001','S03','水位 Z','HydroPro-300','±1 cm','—','offline'],
    ['SNR-8003','S08','流速 V','Sontek-M9','±0.5%','94.2%','online'],
    ['SNR-8004','S08','水温','TempLog-I','±0.1℃','99.9%','online'],
  ];
  return (
    <>
      <div className="page-head">
        <h1>传感器管理</h1>
        <span className="sub">// 617 台 · 593 在线 · 24 离线</span>
        <span className="sp"/>
        <button className="btn">{I.download}导出</button>
        <button className="btn primary">{I.plus}绑定设备</button>
      </div>
      <div className="grid g-4" style={{marginBottom:16}}>
        <KPICard label="设备总数" value="617" color="#49e1ff" seed={4}/>
        <KPICard label="在线率" value="96.1%" delta="+0.3%" color="#2bd99f" seed={6}/>
        <KPICard label="标定到期 (30d)" value="38" color="#ffb547" seed={2}/>
        <KPICard label="平均精度" value="99.1%" color="#49e1ff" seed={3}/>
      </div>
      <div className="toolbar">
        <div className="input" style={{width:280}}><span className="ico">{I.search}</span><input placeholder="SN / 站点 / 型号"/></div>
        <span className="tag info">全部类型</span>
        <span className="tag">全部厂商</span>
        <span className="sp" style={{flex:1}}/>
      </div>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>SN</th><th>绑定站点</th><th>指标</th><th>型号</th><th>精度</th><th>质量</th><th>状态</th><th></th></tr></thead>
          <tbody>{rows.map((r,i)=>(
            <tr key={i}>
              <td className="mono" style={{color:'var(--brand-2)'}}>{r[0]}</td>
              <td>{r[1]}</td>
              <td className="soft">{r[2]}</td>
              <td className="mono muted" style={{fontSize:11.5}}>{r[3]}</td>
              <td className="mono">{r[4]}</td>
              <td>
                {r[5]!=='—' && <div style={{display:'flex',alignItems:'center',gap:8}}>
                  <div className="progress" style={{width:80}}><div className="bar" style={{width:r[5]}}/></div>
                  <span className="mono muted" style={{fontSize:11}}>{r[5]}</span>
                </div>}
              </td>
              <td><span className={`tag ${r[6]==='online'?'info':'danger'}`}><span className={`dot ${r[6]==='online'?'ok':'danger'}`}/>{r[6]==='online'?'在线':'离线'}</span></td>
              <td style={{textAlign:'right'}}><button className="btn sm ghost">详情 {I.chevR}</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}

function ObservationPage() {
  const rows = Array.from({length:10}).map((_,i)=>{
    const h = 14 - Math.floor(i/4);
    const m = (59 - (i*7)%60).toString().padStart(2,'0');
    return [`2026-04-19 ${h}:${m}:00`,'S05',(28.92-i*0.03).toFixed(2),(3.8-i*0.1).toFixed(1),(2.12-i*0.02).toFixed(2),'18.4'];
  });
  return (
    <>
      <div className="page-head">
        <h1>观测数据</h1>
        <span className="sub">// 时序查询 · 聚合 · 导出</span>
        <span className="sp"/>
        <button className="btn">{I.download}导出 CSV</button>
        <button className="btn primary">订阅实时</button>
      </div>
      <div className="card" style={{marginBottom:16}}>
        <div className="card-body" style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr 1fr auto',gap:12}}>
          <div><span className="label-small">站点</span><div className="input"><input defaultValue="S05 黄陂站"/></div></div>
          <div><span className="label-small">指标</span><div className="input"><input defaultValue="水位 Z · 雨量 P · 流速 V"/></div></div>
          <div><span className="label-small">时间范围</span><div className="input"><input defaultValue="近 24 小时"/></div></div>
          <div><span className="label-small">聚合</span><div className="input"><input defaultValue="5 分钟平均"/></div></div>
          <div style={{display:'flex',alignItems:'flex-end'}}><button className="btn primary">查询</button></div>
        </div>
      </div>
      <div className="grid g-12" style={{marginBottom:16}}>
        <div className="card" style={{gridColumn:'span 8'}}>
          <div className="card-head"><span className="title">趋势图 · 水位 / 雨量 / 流速</span><span className="mono">5min · 24h</span></div>
          <div className="card-body"><GlowLine seeds={[1,7,13]} colors={['#49e1ff','#2bd99f','#ffb547']} height={260} animate/></div>
        </div>
        <div className="card" style={{gridColumn:'span 4'}}>
          <div className="card-head"><span className="title">统计摘要</span></div>
          <div className="card-body" style={{display:'grid',gap:10}}>
            {[['最大水位','29.34 m','+0.84 m'],['最小水位','27.11 m','—'],['平均水位','28.46 m','+0.22 m'],['累积雨量','86 mm','24h'],['峰值流速','3.24 m/s','13:18']].map((r,i)=>(
              <div key={i} style={{display:'flex',justifyContent:'space-between',padding:'8px 0',borderBottom: i<4?'1px dashed var(--line)':''}}>
                <span className="soft" style={{fontSize:12.5}}>{r[0]}</span>
                <span className="mono" style={{fontWeight:600,color:'var(--brand-2)'}}>{r[1]}</span>
                <span className="mono muted" style={{fontSize:11}}>{r[2]}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>时间</th><th>站点</th><th>水位 (m)</th><th>雨量 (mm)</th><th>流速 (m/s)</th><th>水温 (℃)</th></tr></thead>
          <tbody>{rows.map((r,i)=>(
            <tr key={i}>
              <td className="mono muted" style={{fontSize:11.5}}>{r[0]}</td>
              <td>{r[1]}</td>
              <td className="mono" style={{fontWeight:600}}>{r[2]}</td>
              <td className="mono">{r[3]}</td>
              <td className="mono">{r[4]}</td>
              <td className="mono">{r[5]}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}

function MapPage() {
  return (
    <>
      <div className="page-head">
        <h1>流域地图</h1>
        <span className="sub">// 实时站点 · 雨量热力 · 水系流线</span>
        <span className="sp"/>
        <button className="btn">图层</button>
        <button className="btn">时间回放</button>
        <button className="btn primary">全屏</button>
      </div>
      <div className="grid g-12">
        <div className="card" style={{gridColumn:'span 3'}}>
          <div className="card-head"><span className="title">图层</span></div>
          <div className="card-body" style={{display:'grid',gap:6}}>
            {[['水系基础',true],['站点标记',true],['雨量热力',true],['流线矢量',true],['行政区划',false],['卫星底图',false],['人口密度',false],['堤坝工程',true]].map((l,i)=>(
              <label key={i} style={{display:'flex',alignItems:'center',gap:10,padding:'8px 10px',borderRadius:6,background:l[1]?'rgba(73,225,255,0.08)':'transparent',cursor:'pointer',fontSize:12.5}}>
                <span className={`switch ${l[1]?'on':''}`}/>
                <span style={{flex:1}}>{l[0]}</span>
              </label>
            ))}
            <div className="divider" style={{margin:'12px 0'}}/>
            <span className="label-small">告警过滤</span>
            <div style={{display:'flex',flexWrap:'wrap',gap:6}}>
              <span className="tag danger">严重 8</span>
              <span className="tag warn">警告 9</span>
              <span className="tag info">已确认 5</span>
            </div>
          </div>
        </div>
        <div className="card" style={{gridColumn:'span 9',padding:0,overflow:'hidden'}}>
          <div style={{height:640,position:'relative'}}>
            <FloodMap height={640}/>
            <div style={{position:'absolute',top:16,left:16,display:'flex',gap:8}}>
              <div className="chip">30.88°N 114.34°E</div>
              <div className="chip">zoom 11</div>
            </div>
            <div style={{position:'absolute',bottom:16,right:16,background:'var(--bg-2)',border:'1px solid var(--line)',borderRadius:8,padding:12,fontSize:11,fontFamily:'var(--font-mono)'}}>
              <div className="muted" style={{marginBottom:6}}>雨量 (mm/h)</div>
              <div style={{display:'flex',alignItems:'center',gap:2}}>
                {[0,10,20,30,40,50].map((v,i)=>(
                  <div key={i} style={{width:24,textAlign:'center'}}>
                    <div style={{height:8,background:`hsl(${200-i*20} 70% 55% / 0.8)`,boxShadow:`0 0 6px hsl(${200-i*20} 70% 55%)`}}/>
                    <div style={{marginTop:4,color:'var(--fg-mute)'}}>{v}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { StationPage, SensorPage, ObservationPage, MapPage });
