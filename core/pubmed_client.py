# simplified_pubmed_client.py
"""
Simplified PubMed Client for Protein Evaluation
"""
import requests
import logging
import re
import time
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class PubMedClient:
    """PubMed API 客户端"""

    def __init__(self):
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.email = "protein.evaluator@example.com"
        self.api_key = None
        self.delay = 0.33  # 默认延迟（3次/秒）
        self.last_request_time = 0

    def _make_request(self, url: str) -> Optional[str]:
        """发送请求"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            self.last_request_time = time.time()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.warning(f"PubMed请求失败: {e}")
            return None

    def get_article_info_simple(self, pubmed_id: str) -> Optional[Dict]:
        """简化的文章信息获取方法"""
        url = f'{self.base_url}/efetch.fcgi?db=pubmed&id={pubmed_id}&retmode=xml&email={self.email}'

        if self.api_key:
            url += f'&api_key={self.api_key}'

        result = self._make_request(url)

        if not result:
            return None

        try:
            article_info = {
                'pubmed_id': pubmed_id,
                'doi': '',
                'title': '',
                'abstract': '',
                'authors': [],
                'journal': '',
                'publication_date': '',
                'pubmed_url': f'https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/'
            }

            # 提取标题
            title_match = re.search(r'<ArticleTitle[^>]*>(.*?)</ArticleTitle>', result, re.DOTALL)
            if title_match:
                article_info['title'] = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

            # 提取DOI
            doi_match = re.search(r'<ArticleId IdType="doi">(.*?)</ArticleId>', result)
            if doi_match:
                article_info['doi'] = doi_match.group(1).strip()

            # 提取摘要
            abstract_parts = []
            abstract_matches = re.findall(r'<AbstractText[^>]*>(.*?)</AbstractText>', result, re.DOTALL)
            for match in abstract_matches:
                clean_text = re.sub(r'<[^>]+>', '', match)
                if clean_text.strip():
                    abstract_parts.append(clean_text.strip())
            if abstract_parts:
                article_info['abstract'] = ' '.join(abstract_parts)

            # 提取期刊信息
            journal_match = re.search(r'<Journal>(.*?)</Journal>', result, re.DOTALL)
            if journal_match:
                journal_title_match = re.search(r'<Title>(.*?)</Title>', journal_match.group(1))
                if journal_title_match:
                    article_info['journal'] = journal_title_match.group(1).strip()

            # 提取作者
            author_matches = re.findall(r'<Author>(.*?)</Author>', result, re.DOTALL)
            for author in author_matches:
                last_name = re.search(r'<LastName>(.*?)</LastName>', author)
                fore_name = re.search(r'<ForeName>(.*?)</ForeName>', author)
                if last_name:
                    name = last_name.group(1).strip()
                    if fore_name:
                        name = f"{fore_name.group(1).strip()} {name}"
                    article_info['authors'].append({'name': name})

            return article_info

        except Exception as e:
            logger.warning(f"解析PubMed文章信息失败 {pubmed_id}: {e}")
            return None
