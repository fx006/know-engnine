<script setup lang="ts">
import { FileUp, Loader2, ScissorsLineDashed } from "@lucide/vue";
import { computed, ref } from "vue";

import {
  importDocument,
  splitDocument,
  type DocumentSplitResult,
  type KnowledgeDocument,
} from "../api/document";

const props = defineProps<{
  apiBaseUrl: string;
  accessToken: string;
  knowledgeBaseId: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  imported: [payload: { document: KnowledgeDocument; split?: DocumentSplitResult }];
}>();

const selectedFile = ref<File | null>(null);
const uploading = ref(false);
const errorMessage = ref("");

const canUpload = computed(
  () =>
    Boolean(selectedFile.value) &&
    Boolean(props.accessToken) &&
    Boolean(props.knowledgeBaseId) &&
    !props.disabled &&
    !uploading.value,
);

function chooseFile(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] || null;
  errorMessage.value = "";
}

async function uploadAndSplit() {
  if (!selectedFile.value || !canUpload.value) {
    return;
  }

  uploading.value = true;
  errorMessage.value = "";

  try {
    const document = await importDocument({
      baseUrl: props.apiBaseUrl,
      accessToken: props.accessToken,
      knowledgeBaseId: props.knowledgeBaseId,
      file: selectedFile.value,
    });

    let split: DocumentSplitResult | undefined;
    if (document.status === "CONVERTED") {
      // quick import 的 md/txt 已转成 converted，可立即切分；PDF/Word 等异步转换后再切。
      split = await splitDocument({
        baseUrl: props.apiBaseUrl,
        accessToken: props.accessToken,
        documentId: document.doc_id,
      });
    }

    emit("imported", { document, split });
    selectedFile.value = null;
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : "文档上传或切分失败";
  } finally {
    uploading.value = false;
  }
}
</script>

<template>
  <section class="document-upload-panel">
    <header class="panel-heading-row">
      <div>
        <span>Document Ingest</span>
        <h2>上传到当前知识库</h2>
      </div>
      <div class="panel-icon">
        <FileUp :size="20" aria-hidden="true" />
      </div>
    </header>

    <label class="file-drop">
      <input
        type="file"
        accept=".md,.markdown,.txt,.pdf,.doc,.docx"
        :disabled="disabled || uploading"
        @change="chooseFile"
      />
      <FileUp :size="24" aria-hidden="true" />
      <strong>{{ selectedFile?.name || "选择文档文件" }}</strong>
      <span>当前第一版优先支持 Markdown / TXT 快速导入并立即切分。</span>
    </label>

    <div class="document-action-row">
      <el-button
        type="primary"
        size="large"
        :disabled="!canUpload"
        :loading="uploading"
        @click="uploadAndSplit"
      >
        <Loader2 v-if="uploading" class="spin" :size="16" aria-hidden="true" />
        <ScissorsLineDashed v-else :size="16" aria-hidden="true" />
        上传并切分
      </el-button>
      <p v-if="!accessToken" class="muted-line">请先登录。</p>
      <p v-else-if="!knowledgeBaseId" class="muted-line">请先选择知识库。</p>
    </div>

    <p v-if="errorMessage" class="form-error">{{ errorMessage }}</p>
  </section>
</template>
