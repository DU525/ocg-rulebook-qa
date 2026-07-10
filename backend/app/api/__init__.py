from flask import Flask

def register_routes(app: Flask):
    from app.api.routes import api
    from app.api.dm_routes import api as dm_api

    app.register_blueprint(api)
    app.register_blueprint(dm_api)

    from app.api.advanced_routes import register_advanced_routes
    advanced_bp = register_advanced_routes()
    app.register_blueprint(advanced_bp)

    from app.api.feedback_routes import register_feedback_routes
    register_feedback_routes(app)

    from app.api.experiment_routes import register_experiment_routes
    register_experiment_routes(app)

    from app.api.admin_routes import register_admin_routes
    register_admin_routes(app)

    from app.api.document_routes import document_api
    app.register_blueprint(document_api)

def init_services():
    """公开初始化服务函数供外部调用"""
    from app.api.routes import init_services as _init
    from app.api.dm_routes import init_dm_services as _dm_init
    _init()
    _dm_init()

def get_services():
    """获取已初始化的服务"""
    from app.api.routes import vector_store, rag_engine, db
    from app.api.dm_routes import dm_vector_store, dm_rag_engine, dm_db
    return vector_store, rag_engine, db, dm_vector_store, dm_rag_engine, dm_db
