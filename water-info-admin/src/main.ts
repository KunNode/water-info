import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'
import { permissionDirective } from './directives/permission'
import { useAppStore } from './stores/app'
import './styles/index.scss'

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)

// Apply persisted theme (FloodMind defaults to dark) before first paint,
// and start watching the system color-scheme for `auto` mode.
{
  const appStore = useAppStore()
  appStore.applyTheme()
  appStore.watchSystemTheme()
}

// Icons are imported on-demand in each component that uses them
// No global registration needed - reduces bundle size

app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.directive('permission', permissionDirective)

app.mount('#app')
