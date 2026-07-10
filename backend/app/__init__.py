# backend/app/__init__.py
from flask import Flask
from flask_cors import CORS
import os
import atexit
import logging

from app.core.logging_config import setup_root_logging, get_logger

def create_app():
    setup_root_logging()

    app = Flask(__name__)

    # 加载配置
    from app.config import Config
    app.config.from_object(Config)

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 确保数据目录存在
    for path in [Config.CHROMA_DB_PATH, Config.UPLOAD_PATH]:
        os.makedirs(path, exist_ok=True)

    from app.core.trace_middleware import init_trace_middleware
    init_trace_middleware(app)

    from app.middleware.request_logging import init_request_logging
    init_request_logging(app)

    from app.api import register_routes, init_services
    
    # 初始化服务
    init_services()
    
    register_routes(app)

    # 启动后台监控调度器
    try:
        from app.core.monitoring_scheduler import start_scheduler
        start_scheduler()
        print("[MONITOR] Monitoring scheduler initialized.")
    except Exception as e:
        print(f"[MONITOR] Failed to start scheduler: {e}")

    # 启动自动维护系统
    try:
        from app.services.auto_maintenance import get_maintenance_system
        system = get_maintenance_system()
        # 暂时不自动启动调度器，用户可以通过API启动
        # system.start()
        print("[MAINTENANCE] Auto maintenance system initialized.")
    except Exception as e:
        print(f"[MAINTENANCE] Failed to initialize auto maintenance: {e}")

    # 应用关闭时优雅停止调度器
    def shutdown_scheduler():
        try:
            from app.core.monitoring_scheduler import stop_scheduler
            stop_scheduler()
            print("[MONITOR] Scheduler stopped gracefully.")
        except Exception:
            pass
        
        try:
            from app.services.auto_maintenance import get_maintenance_system
            system = get_maintenance_system()
            system.stop()
            print("[MAINTENANCE] Auto maintenance system stopped gracefully.")
        except Exception:
            pass

    atexit.register(shutdown_scheduler)

    return app