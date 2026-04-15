import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import NProgress from 'nprogress'
import 'nprogress/nprogress.css'
import { getToken } from '@/utils/storage'

NProgress.configure({ showSpinner: false })

const Layout = () => import('@/layout/index.vue')

export const constantRoutes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', hidden: true },
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '数据大盘', icon: 'Odometer', affix: true },
      },
    ],
  },
  {
    path: '/monitor',
    component: Layout,
    redirect: '/monitor/station',
    meta: { title: '监测管理', icon: 'Monitor' },
    children: [
      {
        path: 'station',
        name: 'Station',
        component: () => import('@/views/station/index.vue'),
        meta: { title: '站点管理', icon: 'MapLocation', roles: ['ADMIN', 'OPERATOR'] },
      },
      {
        path: 'sensor',
        name: 'Sensor',
        component: () => import('@/views/sensor/index.vue'),
        meta: { title: '传感器管理', icon: 'Cpu', roles: ['ADMIN', 'OPERATOR'] },
      },
    ],
  },
  {
    path: '/data',
    component: Layout,
    redirect: '/data/observation',
    meta: { title: '监测数据', icon: 'DataLine' },
    children: [
      {
        path: 'observation',
        name: 'Observation',
        component: () => import('@/views/observation/index.vue'),
        meta: { title: '观测数据', icon: 'DataAnalysis' },
      },
    ],
  },
  {
    path: '/warning',
    component: Layout,
    redirect: '/warning/alarm',
    meta: { title: '告警管理', icon: 'Bell' },
    children: [
      {
        path: 'alarm',
        name: 'Alarm',
        component: () => import('@/views/alarm/index.vue'),
        meta: { title: '告警列表', icon: 'AlarmClock' },
      },
      {
        path: 'threshold',
        name: 'Threshold',
        component: () => import('@/views/threshold/index.vue'),
        meta: { title: '阈值规则', icon: 'Setting', roles: ['ADMIN', 'OPERATOR'] },
      },
    ],
  },
  {
    path: '/ai',
    component: Layout,
    redirect: '/ai/command',
    meta: { title: 'AI指挥', icon: 'MagicStick' },
    children: [
      {
        path: 'command',
        name: 'AICommand',
        component: () => import('@/views/ai/command/index.vue'),
        meta: { title: '智能指挥台', icon: 'ChatDotRound' },
      },
      {
        // Route with optional sessionId parameter for deep linking
        path: 'command/:sessionId',
        name: 'AICommandSession',
        component: () => import('@/views/ai/command/index.vue'),
        meta: { title: '智能指挥台', icon: 'ChatDotRound', hidden: true },
      },
      {
        path: 'plan',
        name: 'AIPlan',
        component: () => import('@/views/ai/plan/index.vue'),
        meta: { title: '预案管理', icon: 'Document' },
      },
    ],
  },
  {
    path: '/map',
    component: Layout,
    children: [
      {
        path: '',
        name: 'Map',
        component: () => import('@/views/map/index.vue'),
        meta: { title: '站点分布', icon: 'Place' },
      },
    ],
  },
  {
    path: '/system',
    component: Layout,
    redirect: '/system/user',
    meta: { title: '系统管理', icon: 'Tools', roles: ['ADMIN'] },
    children: [
      {
        path: 'user',
        name: 'SystemUser',
        component: () => import('@/views/system/user/index.vue'),
        meta: { title: '用户管理', icon: 'User', roles: ['ADMIN'] },
      },
      {
        path: 'role',
        name: 'SystemRole',
        component: () => import('@/views/system/role/index.vue'),
        meta: { title: '角色管理', icon: 'UserFilled', roles: ['ADMIN'] },
      },
      {
        path: 'org',
        name: 'SystemOrg',
        component: () => import('@/views/system/org/index.vue'),
        meta: { title: '组织机构', icon: 'OfficeBuilding', roles: ['ADMIN'] },
      },
      {
        path: 'dept',
        name: 'SystemDept',
        component: () => import('@/views/system/dept/index.vue'),
        meta: { title: '部门管理', icon: 'School', roles: ['ADMIN'] },
      },
      {
        path: 'log',
        name: 'SystemLog',
        component: () => import('@/views/system/log/index.vue'),
        meta: { title: '操作日志', icon: 'Notebook', roles: ['ADMIN'] },
      },
    ],
  },
  {
    path: '/bigscreen',
    name: 'BigScreen',
    component: () => import('@/views/bigscreen/index.vue'),
    meta: { title: '数据大屏', hidden: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '404', hidden: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes: constantRoutes,
  scrollBehavior: () => ({ top: 0 }),
})

// Navigation guard
const whiteList = ['/login']

router.beforeEach((to, _from, next) => {
  NProgress.start()
  document.title = `${to.meta.title || ''} - 智慧水利管理系统`

  const token = getToken()
  if (token) {
    if (to.path === '/login') {
      next({ path: '/' })
    } else {
      next()
    }
  } else {
    if (whiteList.includes(to.path)) {
      next()
    } else {
      next(`/login?redirect=${to.path}`)
    }
  }
})

router.afterEach(() => {
  NProgress.done()
})

export default router
