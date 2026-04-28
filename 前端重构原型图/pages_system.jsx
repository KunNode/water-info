// System: User / Role / Org / Dept / Log

function UserPage() {
  return (
    <>
      <div className="wf-page-head">
        <h1>用户管理</h1>
        <span className="sub">// system / user · 68 人</span>
        <span className="spacer"/>
        <button className="btn">批量导入</button>
        <button className="btn primary">+ 新增用户</button>
      </div>
      <Toolbar>
        <SearchField placeholder="用户名 / 姓名 / 手机" w={260}/>
        <Select label="角色" value="全部"/>
        <Select label="部门" value="全部"/>
        <Select label="状态" value="启用"/>
        <button className="btn">查询</button>
      </Toolbar>
      <Table
        cols={['#','账号','姓名','角色','部门','手机','最近登录','状态','操作']}
        rows={[
          ['1','admin','王洪','ADMIN','运维组','138****2011','14:05',<span><StatusDot state="ok"/>启用</span>,'编辑 · 重置 · 停用'],
          ['2','ops01','李月','OPERATOR','值班组','138****3320','14:22',<span><StatusDot state="ok"/>启用</span>,'编辑 · 重置 · 停用'],
          ['3','ops02','张川','OPERATOR','值班组','138****8891','13:58',<span><StatusDot state="ok"/>启用</span>,'编辑 · 重置 · 停用'],
          ['4','view01','陈颖','VIEWER','气象局','138****4402','昨日',<span><StatusDot state="ok"/>启用</span>,'编辑 · 重置 · 停用'],
          ['5','view02','刘波','VIEWER','应急办','138****7712','4-15',<span><StatusDot state="warn"/>停用</span>,'编辑 · 启用'],
        ]}
      />
      <Pagination/>
    </>
  );
}

function RolePage() {
  return (
    <>
      <div className="wf-page-head">
        <h1>角色管理</h1>
        <span className="sub">// system / role · RBAC</span>
        <span className="spacer"/>
        <button className="btn primary">+ 新建角色</button>
      </div>
      <div className="grid" style={{gridTemplateColumns:'300px 1fr',gap:14}}>
        <div className="box">
          <div className="hd"><span className="t">角色列表</span><span className="mono">3</span></div>
          <div>
            {[
              ['ADMIN','超级管理员','active'],
              ['OPERATOR','操作员'],
              ['VIEWER','观察者'],
            ].map((r,i) => (
              <div key={i} style={{padding:'12px 14px',borderBottom:'1px solid var(--line-soft)',borderLeft: i===0?'3px solid var(--blue)':'3px solid transparent',background: i===0?'var(--blue-wash)':'transparent',cursor:'pointer'}}>
                <div style={{fontWeight:600}}>{r[0]}</div>
                <div style={{fontSize:12,color:'var(--ink-mute)',fontFamily:'var(--font-mono)'}}>{r[1]}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="box">
          <div className="hd"><span className="t">ADMIN · 权限配置</span><span className="mono">全部 · 38 项</span></div>
          <div className="bd">
            {[
              ['监测','站点查询','站点编辑','传感器查询','传感器编辑'],
              ['数据','观测查询','观测导出','订阅'],
              ['告警','告警查询','告警确认','告警关闭','阈值规则编辑'],
              ['AI','AI 对话','预案生成','预案审批','预案执行'],
              ['系统','用户管理','角色管理','部门管理','组织管理','操作日志'],
            ].map((g,i) => (
              <div key={i} style={{padding:'12px 0',borderBottom:'1px dashed var(--line-soft)'}}>
                <div style={{fontFamily:'var(--font-mono)',fontSize:11,color:'var(--ink-mute)',letterSpacing:'0.08em',textTransform:'uppercase',marginBottom:8}}>{g[0]}</div>
                <div style={{display:'flex',flexWrap:'wrap',gap:8}}>
                  {g.slice(1).map((p,j) => (
                    <label key={j} style={{display:'inline-flex',alignItems:'center',gap:6,border:'1px solid var(--line-soft)',padding:'4px 10px',borderRadius:3,fontSize:12}}>
                      <input type="checkbox" defaultChecked/> {p}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div style={{padding:'12px 14px',borderTop:'1px solid var(--line-soft)',display:'flex',justifyContent:'flex-end',gap:8}}>
            <button className="btn">取消</button>
            <button className="btn primary">保存权限</button>
          </div>
        </div>
      </div>
    </>
  );
}

function OrgDeptPage() {
  return (
    <>
      <div className="wf-page-head">
        <h1>组织 / 部门</h1>
        <span className="sub">// system / org + dept</span>
        <span className="spacer"/>
        <button className="btn">新增部门</button>
        <button className="btn primary">+ 新增组织</button>
      </div>
      <div className="grid" style={{gridTemplateColumns:'320px 1fr',gap:14}}>
        <div className="box">
          <div className="hd"><span className="t">组织架构</span></div>
          <div className="bd" style={{fontSize:13,lineHeight:2}}>
            <div>├ <strong>武汉市水务局</strong></div>
            <div style={{paddingLeft:16}}>├ 指挥中心</div>
            <div style={{paddingLeft:16}}>├ 运维组 <span style={{color:'var(--ink-mute)'}}>· 12 人</span></div>
            <div style={{paddingLeft:16}}>├ <strong style={{color:'var(--blue)'}}>值班组 · active · 18 人</strong></div>
            <div style={{paddingLeft:16}}>└ 数据组 · 8 人</div>
            <div>├ 黄陂分局</div>
            <div style={{paddingLeft:16}}>├ 外业组 · 10 人</div>
            <div style={{paddingLeft:16}}>└ 抢险 A/B/C 队 · 24 人</div>
            <div>├ 合作单位</div>
            <div style={{paddingLeft:16}}>├ 气象局</div>
            <div style={{paddingLeft:16}}>└ 应急办</div>
          </div>
        </div>
        <div className="box">
          <div className="hd"><span className="t">值班组 · 部门详情</span><span className="mono">18 人 · 4 角色</span></div>
          <div className="bd" style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:16}}>
            <div>
              <FormRow label="部门名称"><Input value="值班组"/></FormRow>
              <FormRow label="编号"><Input value="DEPT-004"/></FormRow>
              <FormRow label="上级"><Input value="武汉市水务局"/></FormRow>
              <FormRow label="负责人"><Input value="李月"/></FormRow>
            </div>
            <div>
              <FormRow label="职责"><Input value="7×24 监控 · 告警响应 · AI 预案审批"/></FormRow>
              <FormRow label="人数"><Input value="18"/></FormRow>
              <FormRow label="排序"><Input value="4"/></FormRow>
              <FormRow label="状态"><Input value="✔ 启用"/></FormRow>
            </div>
          </div>
          <div style={{padding:'12px 14px',borderTop:'1px solid var(--line-soft)',display:'flex',justifyContent:'flex-end',gap:8}}>
            <button className="btn">取消</button>
            <button className="btn primary">保存</button>
          </div>
        </div>
      </div>
    </>
  );
}

function LogPage() {
  return (
    <>
      <div className="wf-page-head">
        <h1>操作日志</h1>
        <span className="sub">// system / log · 审计追踪</span>
        <span className="spacer"/>
        <button className="btn">导出 CSV</button>
      </div>
      <Toolbar>
        <SearchField placeholder="关键词 / IP / 账号" w={260}/>
        <Select label="模块" value="全部"/>
        <Select label="操作" value="全部"/>
        <Select label="时间" value="今日"/>
        <Select label="结果" value="全部"/>
        <button className="btn">查询</button>
      </Toolbar>
      <Table
        cols={['时间','账号','IP','模块','操作','对象','结果','耗时']}
        rows={[
          ['14:22:11','admin','10.1.2.9','告警','确认','ALM-0012',<span className="tag blue">ok</span>,'80ms'],
          ['14:20:45','admin','10.1.2.9','AI','生成预案','PLAN-0419-A',<span className="tag blue">ok</span>,'7.1s'],
          ['14:18:03','system','—','告警','触发','S005 水位',<span className="tag blue">ok</span>,'40ms'],
          ['14:12:30','ops01','10.1.2.41','传感器','编辑','SN-88210',<span className="tag blue">ok</span>,'120ms'],
          ['14:05:10','admin','10.1.2.9','登录','login','—',<span className="tag blue">ok</span>,'220ms'],
          ['13:58:01','view02','10.1.2.88','登录','login','—',<span className="tag danger">fail</span>,'180ms'],
          ['13:50:22','ops02','10.1.2.64','阈值','编辑','RULE-003',<span className="tag blue">ok</span>,'95ms'],
          ['13:40:11','admin','10.1.2.9','用户','启用','view01',<span className="tag blue">ok</span>,'60ms'],
        ]}
        dense
      />
      <Pagination/>
    </>
  );
}

Object.assign(window, { UserPage, RolePage, OrgDeptPage, LogPage });
