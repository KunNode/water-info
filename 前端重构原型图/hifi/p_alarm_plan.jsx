// Alarm management + Threshold rules + Plan

function AlarmPage() {
  const rows = [
    ['ALM-24190418','14:18:02','crit','S05 黄陂站','超警戒水位 +0.42m','水位','open','张三'],
    ['ALM-24190417','14:11:33','crit','S10 前川站','1h 雨量 38mm 突破阈值','雨量','open','—'],
    ['ALM-24190416','13:54:08','warn','S03 祁家湾','传感器离线 > 10 min','设备','ack','李四'],
    ['ALM-24190415','13:32:51','warn','S08 木兰站','流速异常波动','流速','ack','李四'],
    ['ALM-24190414','13:05:17','warn','S05 黄陂站','水位持续上涨 6h','水位','open','张三'],
    ['ALM-24190413','12:40:22','warn','S12 盘龙城','设备电量低 (18%)','设备','open','—'],
    ['ALM-24190412','12:11:09','info','S07 长轩岭','误报复核完成','杂项','closed','王五'],
    ['ALM-24190411','11:54:42','warn','S14 六指街','传感器数据漂移','雨量','ack','赵六'],
    ['ALM-24190410','11:22:01','info','S02 前川桥','心跳恢复','设备','closed','—'],
  ];
  return (
    <>
      <div className="page-head">
        <h1>告警管理</h1>
        <span className="sub">// 17 open · 5 ack · 142 closed (24h)</span>
        <span className="sp"/>
        <button className="btn ghost">{I.download}导出</button>
        <button className="btn">{I.filter}筛选</button>
        <button className="btn primary">批量确认</button>
      </div>

      <div className="grid g-4" style={{marginBottom:16}}>
        <KPICard label="严重告警" value="8" delta="+3 · 1h" color="#ff5a6a" seed={11}/>
        <KPICard label="警告" value="9" delta="+2 · 1h" color="#ffb547" seed={5}/>
        <KPICard label="已确认" value="5" delta="平均响应 4.2 min" deltaDir="down" color="#49e1ff" seed={3}/>
        <KPICard label="已关闭" value="142" delta="+18 · 今日" color="#2bd99f" seed={7}/>
      </div>

      <div className="toolbar">
        <div className="input" style={{width:280}}>
          <span className="ico">{I.search}</span>
          <input placeholder="告警编号 / 站点 / 描述"/>
        </div>
        <span className="tag danger">严重 8</span>
        <span className="tag warn">警告 9</span>
        <span className="tag info">已确认 5</span>
        <span className="tag">全部类别</span>
        <span className="sp" style={{flex:1}}/>
        <span className="mono muted" style={{fontSize:11}}>最近更新 14:22:08</span>
      </div>

      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr>
            <th>编号</th><th>时间</th><th>级别</th><th>站点</th><th>描述</th><th>类型</th><th>状态</th><th>处置人</th><th></th>
          </tr></thead>
          <tbody>
            {rows.map((r,i) => (
              <tr key={i}>
                <td className="mono" style={{color:'var(--fg-soft)',fontSize:11.5}}>{r[0]}</td>
                <td className="mono muted" style={{fontSize:11.5}}>{r[1]}</td>
                <td>
                  <span className={`tag ${r[2]==='crit'?'danger':r[2]==='warn'?'warn':'info'}`}>
                    <span className={`dot ${r[2]==='crit'?'danger':r[2]==='warn'?'warn':'ok'}`}/>
                    {r[2].toUpperCase()}
                  </span>
                </td>
                <td>{r[3]}</td>
                <td>{r[4]}</td>
                <td><span className="tag">{r[5]}</span></td>
                <td>
                  <span className={`tag ${r[6]==='open'?'danger':r[6]==='ack'?'warn':''}`}>
                    {r[6]==='open'?'未处理':r[6]==='ack'?'已确认':'已关闭'}
                  </span>
                </td>
                <td className="soft">{r[7]}</td>
                <td style={{textAlign:'right'}}>
                  <button className="btn sm">详情 {I.chevR}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function ThresholdPage() {
  const rules = [
    ['水位','Z','≥','警戒水位','28.50 m','短信 · 电话 · 大屏','on'],
    ['水位','Z','≥','保证水位','30.20 m','短信 · 电话 · 预案触发','on'],
    ['雨量','P','≥','1h 累积','30 mm','短信 · 大屏','on'],
    ['雨量','P','≥','3h 累积','60 mm','短信 · 电话','on'],
    ['雨量','P','≥','24h 累积','100 mm','短信 · 电话 · 预案触发','on'],
    ['流速','V','≥','突变阈值','3.2 m/s','短信','off'],
    ['设备','D','=','离线 > 10min','','短信','on'],
    ['设备','D','≤','电量阈值','20%','短信','on'],
  ];
  return (
    <>
      <div className="page-head">
        <h1>阈值规则</h1>
        <span className="sub">// 8 rule · 6 active</span>
        <span className="sp"/>
        <button className="btn">导入模板</button>
        <button className="btn primary">{I.plus}新建规则</button>
      </div>

      <div className="grid g-12" style={{marginBottom:16}}>
        <div className="card" style={{gridColumn:'span 8'}}>
          <div className="card-head"><span className="title">水位 · 阈值带示意</span><span className="mono">S05 黄陂站</span></div>
          <div className="card-body" style={{position:'relative'}}>
            <GlowLine seeds={[2]} colors={['#49e1ff']} height={180} animate/>
            <div style={{position:'absolute',left:16,right:16,top:40,borderTop:'1px dashed #ffb547',textAlign:'right',color:'#ffb547',fontSize:10,fontFamily:'var(--font-mono)'}}>警戒 28.50 m</div>
            <div style={{position:'absolute',left:16,right:16,top:72,borderTop:'1px dashed #ff5a6a',textAlign:'right',color:'#ff5a6a',fontSize:10,fontFamily:'var(--font-mono)'}}>保证 30.20 m</div>
          </div>
        </div>
        <div className="card" style={{gridColumn:'span 4'}}>
          <div className="card-head"><span className="title">规则快速配置</span></div>
          <div className="card-body" style={{display:'grid',gap:10}}>
            <div><span className="label-small">指标</span><div className="input"><input defaultValue="水位 Z"/></div></div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
              <div><span className="label-small">运算</span><div className="input"><input defaultValue="≥"/></div></div>
              <div><span className="label-small">阈值</span><div className="input"><input defaultValue="28.50 m"/></div></div>
            </div>
            <div><span className="label-small">通知渠道</span><div className="input"><input defaultValue="短信 · 电话 · 大屏"/></div></div>
            <button className="btn primary" style={{marginTop:8}}>保存规则</button>
          </div>
        </div>
      </div>

      <div className="tbl-wrap">
        <table className="tbl">
          <thead><tr><th>指标</th><th>符号</th><th>运算</th><th>规则</th><th>阈值</th><th>通知</th><th>状态</th><th></th></tr></thead>
          <tbody>{rules.map((r,i)=>(
            <tr key={i}>
              <td>{r[0]}</td>
              <td className="mono brand" style={{color:'var(--brand-2)'}}>{r[1]}</td>
              <td className="mono">{r[2]}</td>
              <td>{r[3]}</td>
              <td className="mono">{r[4]}</td>
              <td className="soft">{r[5]}</td>
              <td><span className={`switch ${r[7]==='on'?'on':''}`}/></td>
              <td style={{textAlign:'right'}}><button className="btn sm ghost">编辑</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}

function PlanPage() {
  const steps = [
    ['T+0',  '告警触发 · AI 风险评估',       'done'],
    ['T+2m', '指挥长审批 · 四级响应',         'done'],
    ['T+5m', '上游拦蓄指令下发 · 水库联调',   'done'],
    ['T+8m', '下游乡镇预警广播 · 短信 · 大喇叭','run'],
    ['T+15m','关键桥梁封闭 · 交警协同',       'pending'],
    ['T+25m','风险区人员转移 · 12 村 · 1.2w 人','pending'],
    ['T+60m','复盘评估 · 预案归档',           'pending'],
  ];
  return (
    <>
      <div className="page-head">
        <h1>应急预案</h1>
        <span className="sub">// PLAN-0419-A · 执行中 · 57%</span>
        <span className="sp"/>
        <button className="btn">{I.download}预案库</button>
        <button className="btn">克隆</button>
        <button className="btn danger">中止</button>
        <button className="btn primary">推进下一步</button>
      </div>

      <div className="grid g-12" style={{marginBottom:16}}>
        <div className="card" style={{gridColumn:'span 4'}}>
          <div className="card-head"><span className="title">预案摘要</span><span className="mono">0419-A</span></div>
          <div className="card-body" style={{display:'grid',gap:12}}>
            <div>
              <span className="label-small">名称</span>
              <div style={{fontWeight:600,fontSize:15}}>黄陂上游拦蓄 + 下游分级转移</div>
            </div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
              <div><span className="label-small">响应级别</span><span className="tag warn">Ⅳ 级</span></div>
              <div><span className="label-small">发起</span><span className="soft">AI · A-05</span></div>
              <div><span className="label-small">指挥长</span><span className="soft">王建国</span></div>
              <div><span className="label-small">启动</span><span className="mono soft">14:05:22</span></div>
            </div>
            <div className="divider"/>
            <div>
              <span className="label-small">进度</span>
              <div className="progress" style={{height:8}}><div className="bar" style={{width:'57%'}}/></div>
              <div style={{display:'flex',justifyContent:'space-between',marginTop:6,fontSize:11,color:'var(--fg-mute)',fontFamily:'var(--font-mono)'}}>
                <span>3 / 7 步骤完成</span><span>ETA 28 min</span>
              </div>
            </div>
            <div className="divider"/>
            <div>
              <span className="label-small">联动部门</span>
              <div style={{display:'flex',flexWrap:'wrap',gap:6,marginTop:4}}>
                {['水利局','气象局','应急办','交警','乡镇','水库调度','广电'].map(t => <span key={t} className="tag">{t}</span>)}
              </div>
            </div>
          </div>
        </div>

        <div className="card" style={{gridColumn:'span 8'}}>
          <div className="card-head"><span className="title">执行时间线</span><span className="mono">7 steps · 57%</span></div>
          <div className="card-body">
            <div className="tl">
              {steps.map((s,i) => (
                <div key={i} className={`tl-item ${s[2]}`}>
                  <div className="t-time">{s[0]} · {s[2]==='done'?'已完成':s[2]==='run'?'进行中':'待执行'}</div>
                  <div className="t-title">{s[1]}</div>
                  {s[2]==='run' && <div className="t-sub">短信网关 3 / 12 乡镇已送达 · 预计剩余 3 分钟</div>}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="grid g-12">
        <div className="card" style={{gridColumn:'span 6'}}>
          <div className="card-head"><span className="title">预案库</span><span className="mono">12 templates</span></div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:1,background:'var(--line)'}}>
            {[['PLAN-A001','滠水流域超警戒','Ⅳ 级','5 次启用'],['PLAN-A002','府河上游暴雨','Ⅲ 级','2 次启用'],['PLAN-A003','城区内涝','Ⅳ 级','8 次启用'],['PLAN-A004','水库泄洪','Ⅱ 级','1 次启用']].map((p,i)=>(
              <div key={i} style={{padding:14,background:'var(--bg-2)'}}>
                <div className="mono" style={{fontSize:10,color:'var(--fg-mute)',letterSpacing:'0.1em'}}>{p[0]}</div>
                <div style={{fontWeight:500,marginTop:4}}>{p[1]}</div>
                <div style={{display:'flex',gap:6,marginTop:8}}>
                  <span className="tag warn">{p[2]}</span>
                  <span className="tag">{p[3]}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="card" style={{gridColumn:'span 6'}}>
          <div className="card-head"><span className="title">资源调度</span><span className="mono">live</span></div>
          <div className="card-body">
            {[['抢险队','12 组','在位 9 · 出动 3','#49e1ff',75],['沙袋储备','38,200 袋','已使用 4,500','#2bd99f',88],['水泵','42 台','在线 40','#49e1ff',95],['应急车辆','26 辆','出动 8','#ffb547',70]].map((r,i)=>(
              <div key={i} style={{marginBottom:14}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',marginBottom:6}}>
                  <span style={{fontWeight:500}}>{r[0]} <span className="muted" style={{fontSize:11,marginLeft:6}}>{r[1]}</span></span>
                  <span className="mono muted" style={{fontSize:11}}>{r[2]}</span>
                </div>
                <div className="progress"><div className="bar" style={{width:`${r[4]}%`,background:r[3],boxShadow:`0 0 8px ${r[3]}`}}/></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { AlarmPage, ThresholdPage, PlanPage });
