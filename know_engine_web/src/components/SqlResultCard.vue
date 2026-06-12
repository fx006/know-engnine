<script setup lang="ts">
import { AlertTriangle, CheckCircle2, Database, Table2 } from "@lucide/vue";

import type { RagReference } from "../types/chat";
import { getSqlDisplayText } from "../utils/references";

const props = defineProps<{
  reference: RagReference;
}>();

function statusTone(): "ok" | "warning" | "error" {
  if (props.reference.success === false || props.reference.error) {
    return "error";
  }
  if (props.reference.truncated) {
    return "warning";
  }
  return "ok";
}

function statusLabel(): string {
  if (props.reference.error) {
    return "查询失败";
  }
  if (props.reference.truncated) {
    return "结果截断";
  }
  return "查询成功";
}
</script>

<template>
  <article class="sql-result-card" :class="statusTone()">
    <header>
      <div class="sql-result-icon">
        <Database :size="18" aria-hidden="true" />
      </div>
      <div>
        <span>Text-to-SQL</span>
        <h3>{{ reference.documentTitle || "结构化查询结果" }}</h3>
      </div>
      <strong class="status-pill" :class="statusTone()">
        <AlertTriangle
          v-if="statusTone() !== 'ok'"
          :size="13"
          aria-hidden="true"
        />
        <CheckCircle2 v-else :size="13" aria-hidden="true" />
        {{ statusLabel() }}
      </strong>
    </header>

    <div class="sql-result-metrics">
      <div>
        <span>Rows</span>
        <strong>{{ reference.rowCount ?? 0 }}</strong>
      </div>
      <div>
        <span>Tables</span>
        <strong>{{ reference.tables?.length || 0 }}</strong>
      </div>
    </div>

    <div v-if="reference.tables?.length" class="sql-table-tags">
      <span v-for="table in reference.tables" :key="table">
        <Table2 :size="13" aria-hidden="true" />
        {{ table }}
      </span>
    </div>

    <p v-if="reference.chunkContent" class="sql-result-summary">
      {{ reference.chunkContent }}
    </p>

    <pre v-if="getSqlDisplayText(reference)"><code>{{ getSqlDisplayText(reference) }}</code></pre>

    <p v-if="reference.error" class="sql-result-error">{{ reference.error }}</p>
  </article>
</template>
