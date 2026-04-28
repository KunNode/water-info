// Monitor: Station + Sensor pages

function StationPage() {
  return (
    <>
      <div className="wf-page-head">
        <h1>站点管理</h1>
        <span className="sub">// monitor / stations · 132 条</span>
        <span className="spacer"/>
        <button className="btn">导入</button>
        <button className="btn">导出</button>
        <button className="btn primary">+ 新建站点</button>
      </div>

      <Toolbar>
        <SearchField placeholder="站点名称 / 编号 / 地址" w={280}/>
        <Select label="流域" value="黄陂 — 滠水"/>
        <Select label="类型" value="全部"/>
        <Select label="状态" value="全部"/>
        <Select label="运营方" value="全部"/>
        <button className="btn">查询</button>
        <button className="btn">重置</button>
      </Toolbar>

      <Table
        cols={['#','编号','名称','类型','流域/位置','传感器','状态','最后上报','操作']}
        rows={[
          ['1','S001','黄陂上游 · 一号站','水文 + 雨量','黄陂 / 30.8°N 114.3°E','4',<span><StatusDot state="ok"/>在线</span>,'14:22:01','编辑 · 查看'],
          ['2','S005','黄陂 · 五号站','水位','黄陂 / 30.7°N 114.4°E','3',<span><StatusDot state="warn"/>警戒</span>,'14:21:58','编辑 · 查看'],
          ['3','S010','滠水口站','水位 + 流速','滠水 / 30.6°N 114.5°E','5',<span><StatusDot state="error"/>告警</span>,'14:22:03','编辑 · 查看'],
          ['4','S003','姚家集','雨量','黄陂 / 30.9°N 114.2°E','2',<span><StatusDot state="offline"/>离线 12m</span>,'14:09:41','编辑 · 查看'],
          ['5','S008','铁铺水文站','水文综合','黄陂 / 30.8°N 114.3°E','6',<span><StatusDot state="ok"/>在线</span>,'14:21:55','编辑 · 查看'],
          ['6','S012','长堰','水位','滠水 / 30.7°N 114.6°E','3',<span><StatusDot state="ok"/>在线</span>,'14:22:00','编辑 · 查看'],
          ['7','S015','蔡店','雨量','黄陂 / 30.9°N 114.3°E','2',<span><StatusDot state="ok"/>在线</span>,'14:21:48','编辑 · 查看'],
          ['8','S021','木兰湖','水位 + 水质','木兰 / 30.8°N 114.5°E','7',<span><StatusDot state="warn"/>警戒</span>,'14:21:52','编辑 · 查看'],
        ]}
      />
      <Pagination/>
    </>
  );
}

function SensorPage() {
  return (
    <>
      <div className="wf-page-head">
        <h1>传感器管理</h1>
        <span className="sub">// monitor / sensors · 617 台</span>
        <span className="spacer"/>
        <button className="btn">批量配置</button>
        <button className="btn primary">+ 新增传感器</button>
      </div>

      <div className="grid g-4" style={{marginBottom:14}}>
        {[
          ['总数','617'],['在线','589'],['离线','21'],['故障/电量低','7'],
        ].map((k,i) => (
          <div key={i} className="box kpi">
            <div className="label">{k[0]}</div>
            <div className="val">{k[1]}</div>
          </div>
        ))}
      </div>

      <Toolbar>
        <SearchField placeholder="传感器编号 / SN" w={260}/>
        <Select label="站点" value="全部"/>
        <Select label="类型" value="水位"/>
        <Select label="在线" value="全部"/>
        <button className="btn">查询</button>
      </Toolbar>

      <Table
        cols={['#','SN','所属站点','类型','量程','精度','电量','信号','状态','操作']}
        rows={[
          ['1','SN-88201','S005','水位计','0-10m','±1cm','82%','-72 dBm',<span><StatusDot state="ok"/>online</span>,'配置 · 校准'],
          ['2','SN-88202','S005','雨量计','0-200 mm/h','±2%','91%','-68 dBm',<span><StatusDot state="ok"/>online</span>,'配置 · 校准'],
          ['3','SN-88210','S010','超声流速','0-5 m/s','±0.5%','74%','-78 dBm',<span><StatusDot state="warn"/>drift</span>,'配置 · 校准'],
          ['4','SN-88215','S003','雨量计','0-200 mm/h','±2%','18%','-90 dBm',<span><StatusDot state="error"/>battery</span>,'配置 · 校准'],
          ['5','SN-88220','S008','水位计','0-10m','±1cm','88%','-65 dBm',<span><StatusDot state="ok"/>online</span>,'配置 · 校准'],
          ['6','SN-88225','S012','水质 pH','0-14','±0.1','77%','-70 dBm',<span><StatusDot state="ok"/>online</span>,'配置 · 校准'],
        ]}
      />
      <Pagination/>
    </>
  );
}

Object.assign(window, { StationPage, SensorPage });
