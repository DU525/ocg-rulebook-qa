"""Regression test for bracketed Japanese card names in Chinese BM25 queries."""

import unittest

import jieba.analyse

from app.services.bm25_engine import BM25Engine


class BracketedCardNameRecallTest(unittest.TestCase):
    def test_exact_card_name_match_outranks_keyword_tie(self):
        card_name = "黒魔導のカーテン"
        query = f"双方无法特殊召唤时能否发动【{card_name}】？"
        generic_terms = jieba.analyse.extract_tags(query, topK=20)

        engine = BM25Engine.__new__(BM25Engine)
        engine._fallback_index = {
            0: {
                "doc_id": "generic-ruling",
                "keywords": generic_terms,
                "content": " ".join(generic_terms) + " unrelated ruling",
                "metadata": {},
            },
            1: {
                "doc_id": "exact-official-faq",
                "keywords": generic_terms,
                "content": " ".join(generic_terms) + " " + card_name,
                "metadata": {},
            },
        }

        results = engine._fallback_search(query, top_k=2)

        self.assertEqual(results[0]["id"], "exact-official-faq")


if __name__ == "__main__":
    unittest.main()
