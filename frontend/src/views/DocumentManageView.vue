<template>
  <section>
    <header class="topbar">
      <div class="page-heading">
        <p class="eyebrow">Knowledge Base Intake</p>
        <h1>文档管理页</h1>
        <p>管理员上传 TXT、Markdown、DOCX、文本型 PDF，并查看解析状态、启用禁用和失败原因。</p>
      </div>
      <span class="status-pill"><i class="status-dot" />Admin Mock</span>
    </header>

    <div class="panel-grid">
      <article class="panel-card span-5">
        <h2>上传入口占位</h2>
        <div class="placeholder-box">后续接入 POST /api/documents/upload</div>
      </article>

      <article class="panel-card span-7">
        <h2>文档状态样例</h2>
        <div class="table-row">
          <strong>逆变器故障案例.docx</strong>
          <span class="tag">ready</span>
          <span>可参与检索</span>
        </div>
        <div class="table-row">
          <strong>组件巡检说明.pdf</strong>
          <span class="tag warn">processing</span>
          <span>解析中</span>
        </div>
        <div class="table-row">
          <strong>扫描图纸.pdf</strong>
          <span class="tag muted">failed</span>
          <span>文本抽取失败</span>
        </div>
      </article>
    </div>
  </section>
</template>
