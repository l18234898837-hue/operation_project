<template>
  <section>
    <header class="topbar">
      <div class="page-heading">
        <p class="eyebrow">Trace Console</p>
        <h1>基础日志页</h1>
        <p>用于管理员查看问答类型、来源片段数量、trace_id、耗时和时间，辅助检索调参和问题定位。</p>
      </div>
      <span class="status-pill"><i class="status-dot" />Trace Mock</span>
    </header>

    <article class="panel-card">
      <h2>日志列表占位</h2>
      <div class="table-row">
        <strong>逆变器 PV 过压常见原因有哪些？</strong>
        <span class="tag">rag</span>
        <span>trace_qa_001</span>
      </div>
      <div class="table-row">
        <strong>组件巡检一般要检查哪些项？</strong>
        <span class="tag">faq</span>
        <span>trace_qa_002</span>
      </div>
      <div class="table-row">
        <strong>帮我查今天实时发电量。</strong>
        <span class="tag warn">fallback</span>
        <span>trace_qa_003</span>
      </div>
    </article>
  </section>
</template>
