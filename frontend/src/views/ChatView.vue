<template>
  <section>
    <header class="topbar">
      <div class="page-heading">
        <p class="eyebrow">User Question Desk</p>
        <h1>智能问答页</h1>
        <p>用于演示用户提问、系统回答、来源引用、追问和拒答状态。当前为 Module 02 页面壳，暂不接真实 RAG 接口。</p>
      </div>
      <span class="status-pill"><i class="status-dot" />Mock Ready</span>
    </header>

    <div class="panel-grid">
      <article class="panel-card span-7">
        <h2>对话区占位</h2>
        <div class="placeholder-box">后续放置用户消息、AI 回答、加载中和兜底状态</div>
      </article>

      <article class="panel-card span-5">
        <h2>推荐问题</h2>
        <div class="question-row">
          <span>逆变器 PV 过压常见原因有哪些？</span>
          <span class="tag">RAG</span>
        </div>
        <div class="question-row">
          <span>组件巡检一般要检查哪些项？</span>
          <span class="tag">FAQ</span>
        </div>
        <div class="question-row">
          <span>帮我查今天实时发电量。</span>
          <span class="tag warn">拒答</span>
        </div>
      </article>

      <article class="panel-card span-12">
        <h2>来源引用区</h2>
        <p>有效回答必须展示文档名、章节或页码、片段摘要和相关性分数。普通用户界面不展示检索调试细节。</p>
      </article>
    </div>
  </section>
</template>
