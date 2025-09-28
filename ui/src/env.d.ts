/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

declare module 'vue-toastification' {
import { App } from 'vue';
import { ToastInterface } from 'vue-toastification/dist/types/types';

    export const useToast: () => ToastInterface
  export default function install(app: App, options?: any): void
}

declare module 'vue-toastification/dist/index.css'
