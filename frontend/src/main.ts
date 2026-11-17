import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { router } from './router'
import App from './App.vue'
import './styles/base.css'
import './styles/theme.css'

const app = createApp(App).use(createPinia()).use(router)
void router.isReady().then(() => app.mount('#app'))
