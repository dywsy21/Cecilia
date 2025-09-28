import { createApp } from 'vue'
import Toast from 'vue-toastification'
import 'vue-toastification/dist/index.css'
import './index.css'
import App from './App.vue'

const app = createApp(App)

// Configure toast notifications
app.use(Toast, {
  position: "top-right",
  timeout: 5000,
  closeOnClick: true,
  pauseOnFocusLoss: true,
  pauseOnHover: true,
  draggable: true,
  draggablePercent: 0.6,
  showCloseButtonOnHover: false,
  hideProgressBar: false,
  closeButton: "button",
  icon: true,
  rtl: false,
  toastDefaults: {
    success: {
      timeout: 3000,
      hideProgressBar: true
    },
    error: {
      timeout: 8000,
      hideProgressBar: false
    },
    info: {
      timeout: 4000
    }
  }
})

// Global error handler
app.config.errorHandler = (error, vm, info) => {
  console.error('Global error:', error, info)
  // You can send error reports here
}

app.mount('#app')
