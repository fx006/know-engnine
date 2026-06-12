<script setup lang="ts">
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  Database,
  HardDrive,
  Loader2,
  RefreshCw,
  Server,
  ShieldAlert,
  WifiOff,
} from "@lucide/vue";
import { computed, onMounted, ref, watch } from "vue";

import {
  getHealthReport,
  type HealthComponent,
  type HealthReport,
} from "../api/health";

const props = defineProps<{
  apiBaseUrl: string;
}>();

const emit = defineEmits<{
  statusChange: [status: "online" | "degraded" | "offline"];
}>();

const report = ref<HealthReport | null>(null);
const loading = ref(false);
const errorMessage = ref("");
const lastCheckedAt = ref("");

const componentOrder = [
  "app",
  "database",
  "redis",
  "minio",
  "elasticsearch",
  "llm",
];

const componentLabels: Record<string, { title: string; subtitle: string }> = {
  app: {
    title: "应用服务",
    subtitle: "FastAPI 进程与基础响应",
  },
  database: {
    title: "关系数据库",
    subtitle: "MySQL / PostgreSQL / 本地测试 DB",
  },
  redis: {
    title: "Redis",
    subtitle: "缓存、Celery broker 与短期记忆",
  },
  minio: {
    title: "MinIO",
    subtitle: "上传文件与文档原始对象存储",
  },
  elasticsearch: {
    title: "Elasticsearch",
    subtitle: "关键词检索与 BM25 索引",
  },
  llm: {
    title: "大模型配置",
    subtitle: "DashScope key、base URL 与模型名",
  },
};

const componentRows = computed(() => {
  const components = report.value?.components || {};
  const knownRows = componentOrder
    .filter((name) => components[name])
    .map((name) => toRow(name, components[name]));
  const extraRows = Object.entries(components)
    .filter(([name]) => !componentOrder.includes(name))
    .map(([name, component]) => toRow(name, component));

  return [...knownRows, ...extraRows];
});

const summary = computed(() => {
  const rows = componentRows.value;
  return {
    ok: rows.filter((item) => item.tone === "ok").length,
    warning: rows.filter((item) => item.tone === "warning").length,
    error: rows.filter((item) => item.tone === "error").length,
    skipped: rows.filter((item) => item.tone === "muted").length,
  };
});

const overallTone = computed(() => {
  if (!report.value) {
    return "muted";
  }
  return report.value.status === "ok" ? "ok" : "warning";
});

onMounted(() => {
  void refresh();
});

watch(
  () => props.apiBaseUrl,
  () => {
    void refresh();
  },
);

async function refresh() {
  loading.value = true;
  errorMessage.value = "";

  try {
    report.value = await getHealthReport(props.apiBaseUrl, true);
    lastCheckedAt.value = new Intl.DateTimeFormat("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date());
    emit("statusChange", report.value.status === "ok" ? "online" : "degraded");
  } catch (error) {
    report.value = null;
    errorMessage.value =
      error instanceof Error ? error.message : "无法读取后端健康状态";
    emit("statusChange", "offline");
  } finally {
    loading.value = false;
  }
}

function toRow(name: string, component: HealthComponent) {
  return {
    key: name,
    name,
    title: componentLabels[name]?.title || name,
    subtitle: componentLabels[name]?.subtitle || "后端健康组件",
    statusText: statusText(component.status),
    tone: statusTone(component.status),
    detail: component.detail,
    error: component.error,
    extra: componentExtra(component),
    recommendation: recommendation(name, component),
  };
}

function statusText(status: string): string {
  if (status === "ok") {
    return "正常";
  }
  if (status === "configured") {
    return "已配置";
  }
  if (status === "skipped") {
    return "未配置";
  }
  if (status === "error") {
    return "异常";
  }
  return status;
}

function statusTone(status: string): "ok" | "warning" | "error" | "muted" {
  if (status === "ok") {
    return "ok";
  }
  if (status === "error") {
    return "error";
  }
  if (status === "skipped") {
    return "muted";
  }
  return "warning";
}

function componentExtra(component: HealthComponent): string[] {
  return Object.entries(component)
    .filter(([key, value]) => !["status", "detail", "error"].includes(key) && value)
    .map(([key, value]) => `${key}: ${String(value)}`);
}

function recommendation(name: string, component: HealthComponent): string {
  if (component.status === "ok") {
    return "当前组件可用，继续观察真实业务请求即可。";
  }

  if (component.status === "configured") {
    if (name === "llm") {
      return "配置已加载但没有真实模型调用；请使用真实 LLM smoke 或聊天请求验证额度、权限和模型可用性。";
    }

    return "配置已加载但没有真实调用；排障时请使用 deep health 或真实 smoke 验证。";
  }

  if (component.status === "skipped") {
    return "当前环境未启用该组件；如果对应能力已进入演示范围，需要先补齐配置。";
  }

  const recommendations: Record<string, string> = {
    database:
      "优先检查 DATABASE_URL、云数据库安全组/白名单、账号权限和连接数限制。",
    redis: "优先检查 REDIS_URL、密码、云 Redis 安全组，以及 Celery broker 是否同源复用。",
    minio:
      "优先检查 MinIO endpoint、bucket、access key、secret key，以及 endpoint 是否能被本机访问。",
    elasticsearch:
      "优先检查 ELASTICSEARCH_URL、端口、防火墙、认证配置；中文分词器属于后续检索质量项。",
    llm: "优先检查 DashScope base URL、API key、模型名和账号额度；不要把原始 key 暴露给前端。",
  };

  return recommendations[name] || "请查看后端日志和该组件的连接配置。";
}
</script>

<template>
  <section class="admin-health">
    <div class="admin-hero">
      <div>
        <div class="eyebrow">Admin Console</div>
        <h1>环境健康中心</h1>
        <p>
          用于确认 FastAPI、数据库、缓存、对象存储、检索组件和大模型配置是否可用。
        </p>
      </div>
      <button class="refresh-button" type="button" :disabled="loading" @click="refresh">
        <Loader2 v-if="loading" class="spin" :size="16" aria-hidden="true" />
        <RefreshCw v-else :size="16" aria-hidden="true" />
        刷新
      </button>
    </div>

    <div v-if="errorMessage" class="health-error">
      <WifiOff :size="18" aria-hidden="true" />
      <div>
        <strong>无法连接健康检查接口</strong>
        <p>{{ errorMessage }}</p>
      </div>
    </div>

    <div class="health-overview">
      <section class="overview-main" :class="overallTone">
        <div class="overview-icon">
          <Loader2
            v-if="loading && !report"
            class="spin"
            :size="26"
            aria-hidden="true"
          />
          <CheckCircle2 v-else-if="overallTone === 'ok'" :size="26" aria-hidden="true" />
          <ShieldAlert v-else :size="26" aria-hidden="true" />
        </div>
        <div>
          <span>整体状态</span>
          <strong>
            {{
              loading && !report
                ? "检查中"
                : !report
                ? "未连接"
                : report.status === "ok"
                  ? "可用"
                  : "降级"
            }}
          </strong>
          <p>
            {{
              loading && !report
                ? "正在执行 deep health，外部云依赖异常时可能需要几秒钟返回。"
                : report?.status === "ok"
                ? "核心依赖连通性正常，可以继续做真实链路验证。"
                : "存在异常或未启用组件，聊天、上传或检索可能失败。"
            }}
          </p>
        </div>
      </section>

      <section class="overview-grid">
        <div class="overview-stat ok">
          <CheckCircle2 :size="18" aria-hidden="true" />
          <span>正常</span>
          <strong>{{ summary.ok }}</strong>
        </div>
        <div class="overview-stat warning">
          <Clock3 :size="18" aria-hidden="true" />
          <span>待验证</span>
          <strong>{{ summary.warning }}</strong>
        </div>
        <div class="overview-stat error">
          <AlertTriangle :size="18" aria-hidden="true" />
          <span>异常</span>
          <strong>{{ summary.error }}</strong>
        </div>
        <div class="overview-stat muted">
          <Activity :size="18" aria-hidden="true" />
          <span>未启用</span>
          <strong>{{ summary.skipped }}</strong>
        </div>
      </section>
    </div>

    <section v-if="report" class="runtime-profile">
      <div>
        <span>应用</span>
        <strong>{{ report.app_name }}</strong>
      </div>
      <div>
        <span>环境</span>
        <strong>{{ report.environment }}</strong>
      </div>
      <div>
        <span>Chat Model</span>
        <strong>{{ report.llm_chat_model }}</strong>
      </div>
      <div>
        <span>Embedding</span>
        <strong>{{ report.embedding_model }}</strong>
      </div>
      <div>
        <span>检查时间</span>
        <strong>{{ lastCheckedAt || "-" }}</strong>
      </div>
    </section>

    <section class="component-grid">
      <article
        v-for="item in componentRows"
        :key="item.key"
        class="component-card"
        :class="item.tone"
      >
        <header>
          <div class="component-icon">
            <Server v-if="item.name === 'app'" :size="20" aria-hidden="true" />
            <Database
              v-else-if="item.name === 'database' || item.name === 'elasticsearch'"
              :size="20"
              aria-hidden="true"
            />
            <HardDrive
              v-else-if="item.name === 'minio'"
              :size="20"
              aria-hidden="true"
            />
            <Activity v-else :size="20" aria-hidden="true" />
          </div>
          <div>
            <h2>{{ item.title }}</h2>
            <p>{{ item.subtitle }}</p>
          </div>
          <span class="status-pill" :class="item.tone">{{ item.statusText }}</span>
        </header>

        <p class="component-detail">{{ item.detail }}</p>

        <div v-if="item.extra.length" class="component-extra">
          <span v-for="extra in item.extra" :key="extra">{{ extra }}</span>
        </div>

        <details v-if="item.error" class="error-detail">
          <summary>
            <AlertTriangle :size="15" aria-hidden="true" />
            查看错误详情
          </summary>
          <pre>{{ item.error }}</pre>
        </details>

        <div class="component-advice">
          <strong>处理建议</strong>
          <p>{{ item.recommendation }}</p>
        </div>
      </article>
    </section>
  </section>
</template>
