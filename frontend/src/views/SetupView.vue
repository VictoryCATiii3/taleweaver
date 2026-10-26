<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ShieldCheck } from 'lucide-vue-next'
import { api } from '@/composables/useApi'
import { usePasswordPolicy } from '@/composables/usePasswordPolicy'
import { configState } from '@/store/config'

const router = useRouter()
const { hint, validate } = usePasswordPolicy()

const username = ref('admin')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const adminExists = ref(false)
const isSettingUp = ref(false)

const passwordError = computed((): string | null => (password.value ? validate(password.value) : null))
const mismatch = computed((): boolean => Boolean(confirmPassword.value) && confirmPassword.value !== password.value)
const canSubmit = computed((): boolean =>
  username.value.trim().length >= 3
  && Boolean(password.value)
  && !passwordError.value
  && confirmPassword.value === password.value,
)

async function checkAdminExists(): Promise<boolean> {
  try {
    return (await api.getBootstrapStatus()).has_admin
  } catch {
    return false
  }
}

async function handleSetup(): Promise<void> {
  if (!canSubmit.value || isSettingUp.value) {
    return
  }
  isSettingUp.value = true
  error.value = ''
  try {
    await api.setupRootAdmin({ username: username.value.trim(), password: password.value })
    router.push('/login')
  } catch (err: any) {
    console.error('Setup failed:', err)
    adminExists.value = await checkAdminExists()
    error.value = err?.message || 'Setup failed. Please check the server log.'
  } finally {
    isSettingUp.value = false
  }
}
</script>

<template>
  <div class="h-full overflow-y-auto bg-[#050b14]">
    <div class="min-h-full flex flex-col items-center justify-center px-4 py-8 sm:p-6">
      <!-- App Branding -->
      <div class="flex flex-col items-center gap-4 sm:gap-6 mb-8 sm:mb-12 select-none animate-fade-in">
        <div class="w-20 h-20 sm:w-24 sm:h-24 bg-aether-primary/10 rounded-[2rem] flex items-center justify-center border border-aether-primary/20 shadow-[0_0_100px_rgba(78,222,163,0.15)]">
          <img src="@/assets/svg/app-logo.svg" class="w-14 h-14 sm:w-16 sm:h-16 drop-shadow-[0_0_15px_rgba(78,222,163,0.5)]" alt="Logo" />
        </div>
        <div class="text-center">
          <h1 class="text-5xl sm:text-6xl font-black text-white font-display tracking-tighter leading-none mb-2">TaleWeaver</h1>
          <span class="text-xs font-bold text-aether-primary/40 tracking-[0.5em] uppercase">Chronicle Intelligence v{{ configState.appVersion }}</span>
        </div>
      </div>

      <div class="w-full max-w-lg p-6 sm:p-10 bg-white/5 border border-white/10 rounded-[2rem] backdrop-blur-2xl shadow-2xl relative overflow-hidden">
        <!-- Glow Effect -->
        <div class="absolute -top-24 -left-24 w-48 h-48 bg-aether-primary/20 rounded-full blur-[80px]"></div>

        <div class="relative z-10">
          <div class="flex items-center gap-4 mb-6 sm:mb-8">
            <div class="p-3 rounded-2xl bg-aether-primary/10 border border-aether-primary/20">
              <ShieldCheck class="w-6 h-6 text-aether-primary" />
            </div>
            <div>
              <h2 class="text-2xl font-black text-white font-display">Root Admin Setup</h2>
              <p class="text-slate-500 text-xs font-bold uppercase tracking-widest">Initialize your TaleWeaver Instance</p>
            </div>
          </div>

          <p class="text-slate-400 text-sm mb-6 sm:mb-8 leading-relaxed">
            Welcome to your new TaleWeaver instance. Before we can weave chronicles, you must establish a
            <strong class="text-slate-200">Root Administrator</strong>. This account will have full control over the system.
          </p>

          <form class="space-y-6" @submit.prevent="handleSetup">
            <div class="space-y-2">
              <label for="setup-username" class="text-xxs font-black text-slate-500 uppercase tracking-widest">Admin Username</label>
              <input
                id="setup-username"
                v-model="username"
                type="text"
                required
                minlength="3"
                maxlength="50"
                autocomplete="username"
                class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-aether-primary/50 transition-all"
              />
            </div>

            <div class="space-y-2">
              <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div class="space-y-2">
                  <label for="setup-password" class="text-xxs font-black text-slate-500 uppercase tracking-widest">Master Password</label>
                  <input
                    id="setup-password"
                    v-model="password"
                    type="password"
                    required
                    autocomplete="new-password"
                    class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-aether-primary/50 transition-all"
                  />
                </div>
                <div class="space-y-2">
                  <label for="setup-confirm" class="text-xxs font-black text-slate-500 uppercase tracking-widest">Confirm Password</label>
                  <input
                    id="setup-confirm"
                    v-model="confirmPassword"
                    type="password"
                    required
                    autocomplete="new-password"
                    class="w-full bg-white/5 border border-white/10 rounded-xl py-3 px-4 text-white focus:outline-none focus:border-aether-primary/50 transition-all"
                  />
                </div>
              </div>
              <p v-if="passwordError" class="text-xs font-bold text-amber-400">{{ passwordError }}</p>
              <p v-else-if="mismatch" class="text-xs font-bold text-amber-400">Passwords do not match.</p>
              <p v-else class="text-xs text-slate-500">{{ hint }}</p>
            </div>

            <div v-if="error" class="text-red-400 text-xs font-bold bg-red-500/10 border border-red-500/20 p-4 rounded-xl flex flex-col gap-2">
              <span>{{ error }}</span>
              <router-link v-if="adminExists" to="/login" class="text-aether-primary hover:underline uppercase tracking-widest text-xxs">Go to Login &rarr;</router-link>
            </div>

            <button
              type="submit"
              :disabled="isSettingUp || !canSubmit"
              class="btn-primary w-full !py-4 shadow-ambient-emerald/20 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span>{{ isSettingUp ? 'Initializing...' : 'Create admin user' }}</span>
            </button>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>
