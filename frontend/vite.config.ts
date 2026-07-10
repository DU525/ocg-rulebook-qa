import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [
    react({
      // 启用Fast Refresh
      fastRefresh: true,
      // 启用Babel插件以提升性能
      babel: {
        plugins: []
      }
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  
  // 性能优化配置
  build: {
    // 目标浏览器
    target: 'es2015',
    
    // 启用CSS代码分割
    cssCodeSplit: true,
    
    // 启用sourcemap用于调试
    sourcemap: false,
    
    // 代码分割策略
    rollupOptions: {
      output: {
        // 手动分包
        manualChunks: {
          // React核心
          'react-vendor': ['react', 'react-dom'],
          // 工具库
          'utils': ['axios', 'zustand'],
          // Markdown
          'markdown': ['react-markdown', 'remark-gfm', 'react-syntax-highlighter'],
          // UI库
          'icons': ['react-icons', 'framer-motion']
        },
        // 文件名哈希
        entryFileNames: 'assets/js/[name]-[hash].js',
        chunkFileNames: 'assets/js/[name]-[hash].js',
        assetFileNames: 'assets/[ext]/[name]-[hash].[ext]'
      }
    },
    
    // 启用 gzip 压缩
    minify: 'esbuild',
    
    // 报告压缩大小
    reportCompressedSize: true,
    
    // chunk大小警告限制
    chunkSizeWarningLimit: 1000
  },
  
  // 开发服务器优化
  server: {
    port: 3000,
    
    // 启用热模块替换
    hmr: {
      overlay: true
    },
    
    // 代理配置
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        secure: false,
        configure: (proxy) => {
          proxy.on('error', (err, req, res) => {
            console.error('[Vite Proxy Error]', err.message);
          });
        },
      },
    },
    
    // 预热请求以提升首次加载速度
    warmup: {
      // 预热的主要模块
      clientFiles: [
        './src/main.tsx',
        './src/App.tsx'
      ]
    }
  },
  
  // 预览服务器配置
  preview: {
    port: 3000,
    open: true
  },
  
  // 优化配置
  optimizeDeps: {
    // 预构建依赖
    include: [
      'react',
      'react-dom',
      'axios',
      'zustand',
      'react-markdown',
      'remark-gfm',
      'react-syntax-highlighter',
      'react-icons'
    ],
    // 排除不需要预构建的包
    exclude: []
  }
})
