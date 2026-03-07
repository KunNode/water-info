import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'
import { permissionDirective } from './directives/permission'
import './styles/index.scss'

const app = createApp(App)
const pinia = createPinia()

// Icons are imported on-demand in each component that uses them
// No global registration needed - reduces bundle size

app.use(pinia)
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.directive('permission', permissionDirective)

app.mount('#app')
