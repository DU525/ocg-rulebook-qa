import os
import subprocess
from pathlib import Path

def download_ocg_rulebook():
    """下载OCG规则书仓库"""
    repo_url = "https://github.com/lucays/ocg-rulebook.git"
    docs_path = Path(__file__).parent.parent.parent / 'data' / 'ocg_rules'

    if not docs_path.exists():
        docs_path.mkdir(parents=True, exist_ok=True)

    temp_path = docs_path / 'temp'

    # 删除旧数据
    if temp_path.exists():
        import shutil
        shutil.rmtree(temp_path)

    # 使用git clone
    result = subprocess.run(
        ['git', 'clone', '--depth', '1', repo_url, str(temp_path)],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        docs_content = temp_path / 'docs'

        if docs_content.exists():
            for rst_file in docs_content.rglob('*.rst'):
                relative = rst_file.relative_to(docs_content)
                dest = docs_path / relative
                dest.parent.mkdir(parents=True, exist_ok=True)

                with open(rst_file, 'r', encoding='utf-8') as src:
                    content = src.read()
                with open(dest, 'w', encoding='utf-8') as dst:
                    dst.write(content)

        import shutil
        shutil.rmtree(temp_path)

        print("OCG规则书下载完成！")
        return True
    else:
        print(f"下载失败: {result.stderr}")
        return False

if __name__ == '__main__':
    download_ocg_rulebook()