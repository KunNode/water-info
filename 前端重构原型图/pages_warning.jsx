// Warning: Alarm + Threshold

function AlarmPage() {
  return (
    <>
      <div className="wf-page-head">
        <h1>告警管理</h1>
        <span className="sub">// warning / alarm · WS live</span>
        <span className="spacer"/>
        <span className="tag danger">17 open</span>
        <span className="tag warn">8 ack</span>
        <span className="tag blue">140 closed</span>
        <button className="btn">批量确认</button>
        <button className="btn primary">配置规则</button>
      </div>

      <Toolbar>
        <SearchField placeholder="关键词 / 站点" w={240}/>
        <Select label="严重级别" value="全部"/>
        <Select label="状态" value="OPEN+ACK"/>
        <Select label="站点" value="全部"/>
        <Select label="时间" value="今日"/>
        <button className="btn">查询</button>
      </Toolbar>

      <Table
        cols={['#','时间','站点','指标','严重','内容','状态','耗时','操作']}
        rows={[
          ['1','14:18:02','S005','水位',<span className="tag danger">CRIT</span>,'超警戒水位 +0.42m',<span><StatusDot state="error"/>OPEN</span>,'4m','确认 · 关闭 · 详情'],
          ['2','14:11:40','S010','雨量',<span className="tag danger">CRIT</span>,'1h 雨量 38mm > 阈值',<span><StatusDot state="error"/>OPEN</span>,'10m','确认 · 关闭 · 详情'],
          ['3','13:54:11','S003','离线',<span className="tag warn">WARN</span>,'传感器离线 > 10 min',<span><StatusDot state="warn"/>ACK</span>,'28m','关闭 · 详情'],
          ['4','13:32:05','S008','流速',<span className="tag warn">WARN</span>,'流速异常波动 Δ=0.8',<span><StatusDot state="warn"/>ACK</span>,'50m','关闭 · 详情'],
          ['5','13:05:22','S005','水位',<span className="tag warn">WARN</span>,'水位持续上涨 6h',<span><StatusDot state="error"/>OPEN</span>,'1h17m','确认 · 详情'],
          ['6','12:40:11','S012','电量',<span className="tag warn">WARN</span>,'设备电量低 18%',<span><StatusDot state="warn"/>ACK</span>,'1h42m','关闭 · 详情'],
          ['7','12:11:02','S007','流速',<span className="tag blue">INFO</span>,'恢复正常',<span><StatusDot state="ok"/>CLOSED</span>,'—','详情'],
        ]}
        dense
      />
      <Pagination/>

      <div className="box" style={{marginTop:18}}>
        <div className="hd"><span className="t">告警详情 · ALM-20260419-0012</span><span className="mono">S005 · 水位 · CRIT</span></div>
        <div className="bd" style={{display:'grid',gridTemplateColumns:'1.2fr 1fr',gap:18}}>
          <div>
            <LineChartPH seeds={[1,4]} colors={['var(--blue)','#d88a8a']} height={180}/>
            <div style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)',marginTop:6}}>
              蓝：水位 / 红：阈值 4.50m — 在 14:18:02 越线
            </div>
          </div>
          <div style={{fontSize:13}}>
            <div style={{fontFamily:'var(--font-mono)',fontSize:10.5,color:'var(--ink-mute)',letterSpacing:'0.06em',textTransform:'uppercase',marginBottom:8}}>状态流转</div>
            <div className="timeline">
              <div className="tl-item done"><div className="lbl">14:18:02</div><div className="t">OPEN · system</div></div>
              <div className="tl-item done"><div className="lbl">14:19:40</div><div className="t">NOTIFY · 值班 ops</div></div>
              <div className="tl-item run"><div className="lbl">14:20:10</div><div className="t">AI 接入 · 生成预案 A</div></div>
              <div className="tl-item"><div className="lbl">—</div><div className="t">ACK</div></div>
              <div className="tl-item"><div className="lbl">—</div><div className="t">CLOSED</div></div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function ThresholdPage() {
  return (
    <>
      <div className="wf-page-head">
        <h1>阈值规则</h1>
        <span className="sub">// warning / threshold · 42 条</span>
        <span className="spacer"/>
        <button className="btn">导入</button>
        <button className="btn primary">+ 新建规则</button>
      </div>

      <Toolbar>
        <SearchField placeholder="规则名称" w={240}/>
        <Select label="指标" value="水位"/>
        <Select label="启用" value="全部"/>
        <button className="btn">查询</button>
      </Toolbar>

      <Table
        cols={['#','规则名','作用站点','指标','触发条件','严重','通知','启用','操作']}
        rows={[
          ['1','黄陂上游 · 超警戒','S001,S005,S008','水位','> 4.50 m · 持续 5min',<span className="tag danger">CRIT</span>,'ops + plan','✔','编辑 · 禁用'],
          ['2','滠水口 · 流速异常','S010','流速','Δ > 0.8 m/s / 10min',<span className="tag warn">WARN</span>,'ops','✔','编辑 · 禁用'],
          ['3','暴雨阈值 · 红色','ALL','雨量','1h > 30mm',<span className="tag danger">CRIT</span>,'ops + 气象','✔','编辑 · 禁用'],
          ['4','传感器离线','ALL','heartbeat','> 10 min 无上报',<span className="tag warn">WARN</span>,'运维','✔','编辑 · 禁用'],
          ['5','电量低','ALL','battery','< 20%',<span className="tag warn">WARN</span>,'运维','✔','编辑 · 禁用'],
          ['6','水质 pH 异常','S021,S025','pH','< 6 或 > 9',<span className="tag warn">WARN</span>,'环保','○','编辑 · 启用'],
        ]}
      />

      <div className="box" style={{marginTop:18}}>
        <div className="hd"><span className="t">新建 / 编辑规则</span><span className="mono">form</span></div>
        <div className="bd" style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:20}}>
          <div>
            <FormRow label="规则名称"><Input value="黄陂上游 · 超警戒"/></FormRow>
            <FormRow label="作用站点"><Input value="S001, S005, S008 (+2)"/></FormRow>
            <FormRow label="指标"><Input value="水位 (m)"/></FormRow>
            <FormRow label="条件">
              <div style={{display:'flex',gap:6}}>
                <Input value=">" w={60}/>
                <Input value="4.50" w={100}/>
                <Input value="持续 5 min" w={130}/>
              </div>
            </FormRow>
            <FormRow label="严重级别"><Input value="CRIT · 红色"/></FormRow>
          </div>
          <div>
            <FormRow label="通知渠道"><Input value="WebSocket + Email + SMS"/></FormRow>
            <FormRow label="通知对象"><Input value="ops 值班组 · 预案智能体"/></FormRow>
            <FormRow label="抑制窗口" hint="相同告警 N 分钟内不重复推送"><Input value="10 min"/></FormRow>
            <FormRow label="自动预案" hint="触发后自动调起 AI 生成预案"><Input value="✔ 启用 · PlanGenerator"/></FormRow>
            <FormRow label="启用"><Input value="✔ 启用"/></FormRow>
          </div>
        </div>
        <div style={{padding:'12px 14px',borderTop:'1px solid var(--line-soft)',display:'flex',justifyContent:'flex-end',gap:8}}>
          <button className="btn">取消</button>
          <button className="btn">保存草稿</button>
          <button className="btn primary">发布规则</button>
        </div>
      </div>
    </>
  );
}

Object.assign(window, { AlarmPage, ThresholdPage });
