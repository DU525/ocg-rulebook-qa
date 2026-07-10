"""数据集下载与质量检查脚本
用于扩展到 10w 数据量时的数据获取和验证
"""
import os
import sys
import json
import hashlib
import logging
from typing import List, Dict, Any
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logger = logging.getLogger(__name__)


class DataQualityChecker:
    """数据质量检查工具"""

    def __init__(self, chunks_file: str):
        self.chunks_file = chunks_file

    def load_chunks(self) -> List[Dict]:
        if not os.path.exists(self.chunks_file):
            raise FileNotFoundError(f"Chunks file not found: {self.chunks_file}")
        with open(self.chunks_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def check_duplicates(self, chunks: List[Dict]) -> List[Dict]:
        """检查重复内容"""
        seen = {}
        duplicates = []
        for chunk in chunks:
            content_hash = hashlib.md5(chunk['content'].encode('utf-8')).hexdigest()
            if content_hash in seen:
                duplicates.append({
                    'chunk_id': chunk['id'],
                    'duplicate_of': seen[content_hash],
                    'content_preview': chunk['content'][:100]
                })
            else:
                seen[content_hash] = chunk['id']
        return duplicates

    def check_empty_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """检查空内容"""
        return [
            {'id': c['id'], 'metadata': c.get('metadata', {})}
            for c in chunks if not c['content'].strip()
        ]

    def check_too_short_chunks(self, chunks: List[Dict], min_length: int = 10) -> List[Dict]:
        """检查过短的分块"""
        return [
            {'id': c['id'], 'length': len(c['content']), 'content': c['content']}
            for c in chunks if len(c['content'].strip()) < min_length
        ]

    def check_too_long_chunks(self, chunks: List[Dict], max_length: int = 2000) -> List[Dict]:
        """检查过长的分块"""
        return [
            {'id': c['id'], 'length': len(c['content'])}
            for c in chunks if len(c['content']) > max_length
        ]

    def run_full_check(self) -> Dict[str, Any]:
        """运行完整的质量检查"""
        chunks = self.load_chunks()
        duplicates = self.check_duplicates(chunks)
        empty = self.check_empty_chunks(chunks)
        too_short = self.check_too_short_chunks(chunks)
        too_long = self.check_too_long_chunks(chunks)

        content_lengths = [len(c['content']) for c in chunks]
        avg_length = sum(content_lengths) / len(content_lengths) if content_lengths else 0

        return {
            'total_chunks': len(chunks),
            'duplicates': {
                'count': len(duplicates),
                'details': duplicates[:10],
            },
            'empty_chunks': len(empty),
            'too_short_chunks': len(too_short),
            'too_long_chunks': len(too_long),
            'content_stats': {
                'avg_length': round(avg_length, 2),
                'min_length': min(content_lengths) if content_lengths else 0,
                'max_length': max(content_lengths) if content_lengths else 0,
            },
            'quality_score': self._calculate_quality_score(
                len(chunks), len(duplicates), len(empty), len(too_short)
            ),
        }

    def _calculate_quality_score(self, total: int, duplicates: int, empty: int, short: int) -> float:
        """计算质量分数（0-100）"""
        if total == 0:
            return 0.0
        issues = duplicates + empty + short
        score = max(0, 100 - (issues / total) * 100)
        return round(score, 2)


def main():
    """运行质量检查"""
    import argparse

    parser = argparse.ArgumentParser(description='数据质量检查工具')
    parser.add_argument('--chunks-file', help='Chunks JSON 文件路径')
    parser.add_argument('--all', action='store_true', help='检查所有已知的 chunks 文件')
    args = parser.parse_args()

    files_to_check = []
    if args.all:
        data_dir = Path(__file__).parent.parent.parent / 'data' / 'chunks'
        files_to_check = list(data_dir.glob('*_chunks.json'))
    elif args.chunks_file:
        files_to_check = [Path(args.chunks_file)]
    else:
        print("请指定 --chunks-file 或 --all")
        return

    for chunks_file in files_to_check:
        print(f"\n{'='*60}")
        print(f"检查文件: {chunks_file}")
        print(f"{'='*60}")

        checker = DataQualityChecker(str(chunks_file))
        result = checker.run_full_check()

        print(f"总块数: {result['total_chunks']}")
        print(f"重复块数: {result['duplicates']['count']}")
        print(f"空块数: {result['empty_chunks']}")
        print(f"过短块数: {result['too_short_chunks']}")
        print(f"过长块数: {result['too_long_chunks']}")
        print(f"平均长度: {result['content_stats']['avg_length']}")
        print(f"质量分数: {result['quality_score']}/100")

        if result['duplicates']['count'] > 0:
            print("\n前 10 个重复块:")
            for dup in result['duplicates']['details'][:10]:
                print(f"  - {dup['chunk_id']} (重复于 {dup['duplicate_of']}): {dup['content_preview']}...")

        if result['quality_score'] < 90:
            print("\n⚠️ 质量分数较低，建议检查数据源")
        else:
            print("\n✅ 数据质量良好")


if __name__ == '__main__':
    main()
