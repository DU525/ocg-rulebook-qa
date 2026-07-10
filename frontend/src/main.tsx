import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { getWebVitalsMonitor } from './modern/services/webVitalsMonitor'

// 初始化性能监控
getWebVitalsMonitor()
console.log('Web Vitals 监控已启动')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)