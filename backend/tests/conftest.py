import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from unittest.mock import MagicMock

# 兼容新版 werkzeug：删除 __version__ 后 Flask test_client 会崩
# 给 werkzeug 注入一个版本字符串，让 Flask.testing 正常初始化
try:
    import werkzeug
    if not hasattr(werkzeug, '__version__'):
        werkzeug.__version__ = '3.0.0'  # 任意非空字符串即可
except ImportError:
    pass

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False

if not HAS_APSCHEDULER:
    mock_apscheduler = MagicMock()
    mock_bg_scheduler = MagicMock()
    mock_bg_scheduler_cls = MagicMock()
    mock_bg_scheduler_cls.return_value = mock_bg_scheduler
    mock_bg_scheduler.add_job = MagicMock()
    mock_bg_scheduler.start = MagicMock()
    mock_bg_scheduler.shutdown = MagicMock()

    sys.modules.setdefault('apscheduler', mock_apscheduler)
    sys.modules.setdefault('apscheduler.schedulers', mock_apscheduler)
    sys.modules.setdefault('apscheduler.schedulers.background', mock_bg_scheduler)
    sys.modules['apscheduler.schedulers.background'].BackgroundScheduler = mock_bg_scheduler_cls
    sys.modules.setdefault('apscheduler.triggers', mock_apscheduler)
    sys.modules.setdefault('apscheduler.triggers.interval', mock_apscheduler)
    sys.modules['apscheduler.triggers.interval'].IntervalTrigger = MagicMock
    sys.modules.setdefault('apscheduler.triggers.cron', mock_apscheduler)
    sys.modules['apscheduler.triggers.cron'].CronTrigger = MagicMock
    sys.modules.setdefault('apscheduler.job', mock_apscheduler)


@pytest.fixture(scope='session', autouse=True)
def _setup_app_once():
    import dotenv
    old_load = dotenv.load_dotenv
    dotenv.load_dotenv = lambda *a, **k: None

    from app.core import monitoring_scheduler
    monitoring_scheduler.start_scheduler = lambda: None

    from app.api import routes
    routes.init_services = lambda: None

    from app.api import dm_routes
    dm_routes.init_dm_services = lambda: None

    dotenv.load_dotenv = old_load


@pytest.fixture
def app(_setup_app_once):
    from app import create_app
    test_app = create_app()
    test_app.config['TESTING'] = True
    yield test_app


@pytest.fixture
def client(app):
    return app.test_client()
