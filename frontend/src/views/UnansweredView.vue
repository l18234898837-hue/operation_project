<template>
  <section>
    <header class="topbar">
      <div class="page-heading">
        <p class="eyebrow">Knowledge Gap Loop</p>
        <h1>未命中问题页</h1>
        <p>收集证据不足、超出范围、信息缺失和无关问题，为 FAQ 维护和知识库补充形成回流闭环。</p>
      </div>
      <span class="status-pill"><i class="status-dot" />Review Mock</span>
    </header>

    <div class="panel-grid">
      <article class="panel-card span-4">
        <h3>证据不足</h3>
        <p>当前知识库没有找到可引用片段，需要补文档或新增 FAQ。</p>
        <span class="tag warn">new</span>
      </article>
      <article class="panel-card span-4">
        <h3>超出范围</h3>
        <p>例如实时发电量、当前告警、SCADA 数据等，第一阶段统一拒答。</p>
        <span class="tag muted">reviewed</span>
      </article>
      <article class="panel-card span-4">
        <h3>信息缺失</h3>
        <p>用户未提供设备类型、故障现象或时间范围，需要触发追问。</p>
        <span class="tag">resolved</span>
      </article>
    </div>
  </section>
</template>
