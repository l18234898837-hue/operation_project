<script setup lang="ts">
import { computed } from "vue";

import { parseAssistantMarkdown, type MarkdownInline } from "../../chat/markdownRenderer";

const props = defineProps<{
  content: string;
}>();

const blocks = computed(() => parseAssistantMarkdown(props.content));

function inlineKey(token: MarkdownInline, index: number) {
  return `${token.type}-${index}-${token.text}`;
}
</script>

<template>
  <div class="markdown-answer">
    <template v-for="(block, blockIndex) in blocks" :key="`${block.type}-${blockIndex}`">
      <component :is="`h${block.level}`" v-if="block.type === 'heading'" class="markdown-heading">
        <template v-for="(token, tokenIndex) in block.inlines" :key="inlineKey(token, tokenIndex)">
          <strong v-if="token.type === 'strong'">{{ token.text }}</strong>
          <code v-else-if="token.type === 'code'">{{ token.text }}</code>
          <template v-else>{{ token.text }}</template>
        </template>
      </component>

      <p v-else-if="block.type === 'paragraph'">
        <template v-for="(token, tokenIndex) in block.inlines" :key="inlineKey(token, tokenIndex)">
          <strong v-if="token.type === 'strong'">{{ token.text }}</strong>
          <code v-else-if="token.type === 'code'">{{ token.text }}</code>
          <template v-else>{{ token.text }}</template>
        </template>
      </p>

      <ol v-else-if="block.type === 'list' && block.kind === 'ordered'">
        <li v-for="(item, itemIndex) in block.items" :key="`ordered-${blockIndex}-${itemIndex}`">
          <template v-for="(token, tokenIndex) in item" :key="inlineKey(token, tokenIndex)">
            <strong v-if="token.type === 'strong'">{{ token.text }}</strong>
            <code v-else-if="token.type === 'code'">{{ token.text }}</code>
            <template v-else>{{ token.text }}</template>
          </template>
        </li>
      </ol>

      <ul v-else-if="block.type === 'list'">
        <li v-for="(item, itemIndex) in block.items" :key="`unordered-${blockIndex}-${itemIndex}`">
          <template v-for="(token, tokenIndex) in item" :key="inlineKey(token, tokenIndex)">
            <strong v-if="token.type === 'strong'">{{ token.text }}</strong>
            <code v-else-if="token.type === 'code'">{{ token.text }}</code>
            <template v-else>{{ token.text }}</template>
          </template>
        </li>
      </ul>

      <pre v-else-if="block.type === 'code'"><code>{{ block.code }}</code></pre>
    </template>
  </div>
</template>
