<script setup lang="ts">
import { LogIn, LogOut, UserRound } from "@lucide/vue";
import { computed, ref } from "vue";

import type { AuthUser } from "../api/auth";

const props = defineProps<{
  user: AuthUser | null;
  loading?: boolean;
  error?: string;
}>();

const emit = defineEmits<{
  login: [payload: { username: string; password: string }];
  logout: [];
}>();

const username = ref("demo_user");
const password = ref("DemoPassword123");

const displayName = computed(
  () => props.user?.nickname || props.user?.username || "未登录",
);

function submitLogin() {
  emit("login", {
    username: username.value.trim(),
    password: password.value,
  });
}
</script>

<template>
  <section class="identity-panel" aria-label="登录信息">
    <header class="identity-header">
      <div class="identity-icon">
        <UserRound :size="18" aria-hidden="true" />
      </div>
      <div>
        <span>Identity</span>
        <strong>{{ displayName }}</strong>
      </div>
      <button
        v-if="user"
        class="text-action"
        type="button"
        :disabled="loading"
        @click="emit('logout')"
      >
        <LogOut :size="15" aria-hidden="true" />
        退出
      </button>
    </header>

    <div v-if="user" class="identity-meta">
      <span>{{ user.userId }}</span>
      <span>{{ user.role }}</span>
      <span>{{ user.status }}</span>
    </div>

    <form v-else class="login-form" @submit.prevent="submitLogin">
      <label>
        <span>用户名</span>
        <el-input
          v-model="username"
          :disabled="loading"
          autocomplete="username"
          spellcheck="false"
        />
      </label>
      <label>
        <span>密码</span>
        <el-input
          v-model="password"
          :disabled="loading"
          autocomplete="current-password"
          show-password
          type="password"
        />
      </label>
      <el-button
        class="login-button"
        type="primary"
        native-type="submit"
        :loading="loading"
      >
        <LogIn :size="16" aria-hidden="true" />
        登录
      </el-button>
    </form>

    <p v-if="error" class="form-error">{{ error }}</p>
  </section>
</template>
