import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { Quasar } from 'quasar'

// Quasar CSS + icon set
import '@quasar/extras/material-icons/material-icons.css'
import 'quasar/dist/quasar.css'

import App from './App.vue'
import './style.css'

const app = createApp(App)
app.use(createPinia())
app.use(Quasar, { plugins: {} })
app.mount('#app')
