import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ProfileView from '../views/ProfileView.vue'
import SetupView from '../views/SetupView.vue'
import InterviewView from '../views/InterviewView.vue'
import HistoryView from '../views/HistoryView.vue'
import ReportView from '../views/ReportView.vue'
import MemoryView from '../views/MemoryView.vue'
import GrowthView from '../views/GrowthView.vue'
import AuthView from '../views/AuthView.vue'
import { installAuthGuard } from './auth'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: AuthView, meta: { title: '登录', authPage: true } },
    { path: '/register', component: AuthView, meta: { title: '注册账号', authPage: true } },
    { path: '/', component: HomeView, meta: { title: '工作台' } },
    { path: '/profile', component: ProfileView, meta: { title: '训练档案' } },
    { path: '/memories', component: MemoryView, meta: { title: '个人偏好' } },
    { path: '/growth', component: GrowthView, meta: { title: '专项练习' } },
    { path: '/practice', component: SetupView, meta: { title: '面试练习' } },
    { path: '/history', component: HistoryView, meta: { title: '训练记录' } },
    { path: '/sessions/:id/report', component: ReportView, meta: { title: '练习总结' } },
    { path: '/sessions/:id', component: InterviewView, meta: { title: '面试室' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: (to, _from, savedPosition) => to.hash ? { el: to.hash, top: 20 } : savedPosition || { top: 0 },
})

installAuthGuard(router)
