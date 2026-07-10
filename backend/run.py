# backend/run.py
import os

# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

# 从环境变量读取配置（必须在 .env 文件中设置）
if not os.environ.get('MINIMAX_API_KEY'):
    print("[WARNING] MINIMAX_API_KEY not set. Please configure it in .env file.")
if not os.environ.get('MINIMAX_API_BASE'):
    os.environ['MINIMAX_API_BASE'] = 'https://api.minimaxi.com/v1/text/chatcompletion_v2'
if not os.environ.get('MODEL_NAME'):
    os.environ['MODEL_NAME'] = 'MiniMax-M2.7'

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)