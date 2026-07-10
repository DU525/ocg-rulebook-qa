import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.vector_store import VectorStore
from app.services.document_processor import DocumentProcessor
from app.db.models import Database, Document
from app.config import Config
import uuid

def init_knowledge_base():
    """初始化知识库"""
    print("开始初始化知识库...")

    vector_store = VectorStore(Config.CHROMA_DB_PATH)
    processor = DocumentProcessor(chunk_size=512, chunk_overlap=64)

    docs_path = Path(Config.DOCS_PATH)

    if not docs_path.exists() or not any(docs_path.rglob('*.rst')):
        print(f"错误: 文档目录不存在或没有文档文件 {docs_path}")
        print("请先运行 download_rules.py 下载规则书")
        return

    all_chunks = []
    file_count = 0

    for rst_file in docs_path.rglob('*.rst'):
        print(f"处理文件: {rst_file}")

        try:
            chunks = processor.process_rst_file(str(rst_file))
            all_chunks.extend(chunks)
            file_count += 1
            print(f"  - 生成 {len(chunks)} 个文档块")
        except Exception as e:
            print(f"  - 处理失败: {e}")

    print(f"\n总计处理 {file_count} 个文件，生成 {len(all_chunks)} 个文档块")

    if all_chunks:
        print("正在添加到向量数据库...")
        vector_store.add_chunks(all_chunks)
        print("添加完成！")

        db = Database(Config.SQLITE_DB_PATH)
        session = db.get_session()

        doc = Document(
            id=str(uuid.uuid4()),
            name="OCG官方规则书",
            source="builtin",
            file_path=str(docs_path),
            status="completed",
            chunk_count=len(all_chunks)
        )
        session.add(doc)
        session.commit()
        session.close()

        print("文档记录已保存")

    stats = vector_store.get_collection_stats()
    print(f"\n知识库统计: {stats}")

if __name__ == '__main__':
    init_knowledge_base()