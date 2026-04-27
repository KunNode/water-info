<template>
  <div class="fm-login">
    <!-- LEFT: Brand showcase with animated SVG -->
    <div class="fm-login__brand">
      <svg class="fm-login__bg" width="100%" height="100%">
        <defs>
          <pattern id="grid-login" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M60 0H0V60" fill="none" stroke="rgba(73,225,255,0.08)" stroke-width="0.5"/>
          </pattern>
          <linearGradient id="wave-login" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#49e1ff" stop-opacity="0.6"/>
            <stop offset="100%" stop-color="#49e1ff" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid-login)"/>
        <path v-for="i in 5" :key="i"
          :d="`M0 ${200+i*80} Q 200 ${150+i*80} 400 ${220+i*80} T 800 ${180+i*80} T 1200 ${220+i*80}`"
          fill="none" stroke="url(#wave-login)" stroke-width="1.5"/>
        <circle v-for="i in 20" :key="`p${i}`"
          :cx="50+i*60" :cy="100+Math.sin(i)*200+i*20" r="1.5" fill="#49e1ff" opacity="0.6">
          <animate attributeName="cy" :values="`${100+i*30};${600+i*30};${100+i*30}`"
            :dur="`${8+i%5}s`" repeatCount="indefinite"/>
          <animate attributeName="opacity" values="0;0.8;0"
            :dur="`${8+i%5}s`" repeatCount="indefinite"/>
        </circle>
      </svg>

      <div class="fm-login__brand-content">
        <div class="fm-login__brand-header">
          <div class="fm-login__brand-mark">F</div>
          <div>
            <div class="fm-login__brand-name">FloodMind</div>
            <div class="fm-label-sm">HYDRO · INTELLIGENCE · PLATFORM</div>
          </div>
        </div>

        <div class="fm-login__brand-body">
          <h1 class="fm-login__slogan">
            让水 <span class="gradient-text">被预见</span>。<br/>
            让决策 <span class="gradient-text">有 AI 托底</span>。
          </h1>
          <p class="fm-login__desc">
            六个智能体协同作业，从监测到预案生成，4 分钟内完成一次完整的防洪应急决策闭环。
          </p>
          <div class="fm-login__stats">
            <div v-for="k in brandStats" :key="k.label" class="fm-login__stat">
              <div class="fm-login__stat-val gradient-text">{{ k.value }}</div>
              <div class="fm-label-sm">{{ k.label }}</div>
            </div>
          </div>
        </div>

        <div class="fm-login__brand-footer">
          <span class="fm-label-sm">© 2026 FLOODMIND · WUHAN HYDRO OPS · v1.0.0</span>
        </div>
      </div>
    </div>

    <!-- RIGHT: Login form -->
    <div class="fm-login__form-side">
      <div class="fm-login__form">
        <h2 class="fm-login__form-title">登录</h2>
        <p class="fm-login__form-subtitle">使用工号或授权账号进入指挥中心</p>

        <form class="fm-login__fields" @submit.prevent="handleLogin">
          <div class="fm-login__field">
            <label class="fm-label-sm">账号</label>
            <div class="fm-login__input" :class="{ focused: focusedField === 'username' }">
              <input v-model="loginForm.username" type="text" placeholder="请输入账号"
                @focus="focusedField = 'username'" @blur="focusedField = ''"/>
            </div>
          </div>

          <div class="fm-login__field">
            <label class="fm-label-sm">密码</label>
            <div class="fm-login__input" :class="{ focused: focusedField === 'password' }">
              <input v-model="loginForm.password" :type="showPassword ? 'text' : 'password'"
                placeholder="请输入密码" @focus="focusedField = 'password'" @blur="focusedField = ''"/>
              <button type="button" class="fm-login__toggle-pw" @click="showPassword = !showPassword">
                {{ showPassword ? '👁' : '👁‍🗨' }}
              </button>
            </div>
          </div>

          <div class="fm-login__field">
            <label class="fm-label-sm">验证码</label>
            <div class="fm-login__captcha">
              <div class="fm-login__input" :class="{ focused: focusedField === 'captcha' }" style="flex:1">
                <input v-model="loginForm.captcha" type="text" placeholder="验证码"
                  @focus="focusedField = 'captcha'" @blur="focusedField = ''"/>
              </div>
              <div class="fm-login__captcha-img" @click="refreshCaptcha">
                {{ captchaText }}
              </div>
            </div>
          </div>

          <div class="fm-login__options">
            <label class="fm-login__remember">
              <span class="fm-switch" :class="{ on: remember }" @click="remember = !remember"/>
              <span class="fm-soft">记住密码</span>
            </label>
            <a class="fm-login__forgot" href="#">忘记密码?</a>
          </div>

          <button type="submit" class="fm-btn fm-btn--primary fm-login__submit" :disabled="loading">
            <span v-if="loading" class="fm-login__spinner"/>
            进入指挥中心
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 6l6 6-6 6"/>
            </svg>
          </button>

          <p class="fm-login__agreement">
            登录即表示同意 <a class="gradient-text" href="#">《数据安全承诺》</a> · 启用双因子
          </p>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const loading = ref(false)
const remember = ref(false)
const showPassword = ref(false)
const focusedField = ref('')
const captchaText = ref('A8X2')

const loginForm = reactive({
  username: '',
  password: '',
  captcha: '',
})

const brandStats = [
  { value: '132', label: '接入站点' },
  { value: '617', label: '传感设备' },
  { value: '6', label: '智能体' },
  { value: '4 min', label: '端到端' },
]

function refreshCaptcha() {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  captchaText.value = Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
}

async function handleLogin() {
  if (!loginForm.username) {
    ElMessage.warning('请输入账号')
    return
  }
  if (!loginForm.password || loginForm.password.length < 6) {
    ElMessage.warning('密码长度不少于6位')
    return
  }

  loading.value = true
  try {
    await userStore.login({
      username: loginForm.username,
      password: loginForm.password,
    })
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/'
    router.push(redirect)
  } catch (err: any) {
    ElMessage.error(err.message || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.fm-login {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  overflow: hidden;
  background: var(--fm-bg-0);
}

/* LEFT: Brand side */
.fm-login__brand {
  position: relative;
  overflow: hidden;
  background: radial-gradient(800px 600px at 30% 40%, rgba(62,166,255,0.25), transparent 60%),
              radial-gradient(600px 500px at 70% 70%, rgba(73,225,255,0.18), transparent 60%),
              linear-gradient(180deg, #05101f 0%, #030812 100%);
}

.fm-login__bg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.fm-login__brand-content {
  position: relative;
  padding: 56px 64px;
  display: flex;
  flex-direction: column;
  height: 100%;
  justify-content: space-between;
  z-index: 1;
}

.fm-login__brand-header {
  display: flex;
  align-items: center;
  gap: 14px;
}

.fm-login__brand-mark {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  background: var(--fm-grad-brand);
  box-shadow: 0 0 24px rgba(73,225,255,0.6);
  display: grid;
  place-items: center;
  font-weight: 700;
  color: #fff;
  font-size: 22px;
  font-family: var(--fm-font-mono);
  position: relative;
  overflow: hidden;

  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 30% 20%, rgba(255,255,255,0.4), transparent 50%);
  }
}

.fm-login__brand-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--fm-fg);
}

.fm-login__brand-body {
  max-width: 600px;
}

.fm-login__slogan {
  font-size: 46px;
  font-weight: 700;
  line-height: 1.15;
  color: var(--fm-fg);
  margin: 0;
}

.gradient-text {
  background: linear-gradient(90deg, var(--fm-brand-2), var(--fm-brand));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

.fm-login__desc {
  color: var(--fm-fg-soft);
  margin-top: 20px;
  line-height: 1.7;
  font-size: 14px;
}

.fm-login__stats {
  display: flex;
  gap: 24px;
  margin-top: 32px;
}

.fm-login__stat {
  .fm-login__stat-val {
    font-size: 28px;
    font-weight: 700;
    font-family: var(--fm-font-mono);
  }
  .fm-label-sm {
    font-size: 11px;
    letter-spacing: 0.1em;
    margin-top: 2px;
    color: var(--fm-fg-mute);
  }
}

.fm-login__brand-footer {
  .fm-label-sm {
    font-size: 11px;
    letter-spacing: 0.15em;
    color: var(--fm-fg-mute);
  }
}

/* RIGHT: Form side */
.fm-login__form-side {
  display: grid;
  place-items: center;
  padding: 40px;
  background: var(--fm-bg-0);
}

.fm-login__form {
  width: 100%;
  max-width: 420px;
}

.fm-login__form-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--fm-fg);
  margin: 0;
}

.fm-login__form-subtitle {
  margin-top: 6px;
  font-size: 13px;
  color: var(--fm-fg-mute);
}

.fm-login__fields {
  margin-top: 32px;
  display: grid;
  gap: 16px;
}

.fm-login__field {
  .fm-label-sm {
    margin-bottom: 6px;
    display: block;
  }
}

.fm-login__input {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 42px;
  padding: 0 14px;
  background: var(--fm-bg-2);
  border: 1px solid var(--fm-line-2);
  border-radius: var(--fm-radius-sm);
  color: var(--fm-fg);
  font-size: 14px;
  transition: all 0.2s;

  &.focused {
    border-color: var(--fm-brand);
    box-shadow: 0 0 0 3px var(--fm-line-glow);
  }

  input {
    flex: 1;
    background: none;
    border: none;
    outline: none;
    color: inherit;
    font: inherit;
    min-width: 0;

    &::placeholder {
      color: var(--fm-fg-mute);
    }
  }
}

.fm-login__toggle-pw {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  opacity: 0.5;
  transition: opacity 0.2s;
  padding: 0;

  &:hover {
    opacity: 1;
  }
}

.fm-login__captcha {
  display: flex;
  gap: 10px;
}

.fm-login__captcha-img {
  width: 110px;
  height: 42px;
  background: linear-gradient(135deg, #0a1628, #06121f);
  border: 1px solid var(--fm-line);
  border-radius: var(--fm-radius-sm);
  display: grid;
  place-items: center;
  font-family: var(--fm-font-mono);
  font-size: 18px;
  letter-spacing: 0.2em;
  color: var(--fm-brand-2);
  font-weight: 700;
  text-decoration: line-through;
  text-decoration-color: rgba(73,225,255,0.3);
  cursor: pointer;
  user-select: none;
}

.fm-login__options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12.5px;
}

.fm-login__remember {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.fm-switch {
  position: relative;
  width: 28px;
  height: 16px;
  border-radius: 8px;
  background: var(--fm-bg-3);
  border: 1px solid var(--fm-line-2);
  cursor: pointer;
  transition: background 0.2s;
  flex-shrink: 0;

  &::after {
    content: '';
    position: absolute;
    top: 2px;
    left: 2px;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--fm-fg-soft);
    transition: all 0.2s;
  }

  &.on {
    background: var(--fm-grad-brand);
    border-color: transparent;

    &::after {
      left: 14px;
      background: #fff;
    }
  }
}

.fm-login__forgot {
  color: var(--fm-brand-2);
  text-decoration: none;
}

.fm-login__submit {
  margin-top: 8px;
  padding: 12px 20px;
  justify-content: center;
  font-size: 14px;
  height: auto;
  width: 100%;
}

.fm-login__spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.fm-login__agreement {
  text-align: center;
  font-size: 11px;
  margin-top: 8px;
  color: var(--fm-fg-mute);

  a {
    color: var(--fm-brand-2);
    text-decoration: none;
  }
}

/* Responsive */
@media (max-width: 1024px) {
  .fm-login {
    grid-template-columns: 1fr;
  }
  .fm-login__brand {
    display: none;
  }
  .fm-login__form-side {
    padding: 24px;
  }
}

@media (max-width: 480px) {
  .fm-login__form {
    max-width: 100%;
  }
  .fm-login__slogan {
    font-size: 32px;
  }
}
</style>
