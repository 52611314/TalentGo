import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import ProfileView from '../views/ProfileView.vue'
import SetupView from '../views/SetupView.vue'
import InterviewView from '../views/InterviewView.vue'
import HistoryView from '../views/HistoryView.vue'
import ReportView from '../views/ReportView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView, meta: { title: '工作台' } },
    { path: '/profile', component: ProfileView, meta: { title: '训练档案' } },
    { path: '/practice', component: SetupView, meta: { title: '面试练习' } },
    { path: '/history', component: HistoryView, meta: { title: '训练记录' } },
    { path: '/sessions/:id/report', component: ReportView, meta: { title: '练习总结' } },
    { path: '/sessions/:id', component: InterviewView, meta: { title: '面试室' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
