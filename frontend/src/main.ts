import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import '@fontsource/caveat/600.css'
import './assets/main.css'
import './assets/portal-theme.css'
import './skins/index.css'

createApp(App).use(router).mount('#app')

