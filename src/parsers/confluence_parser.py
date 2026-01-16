# src/parsers/confluence_parser.py

from atlassian import Confluence
from typing import Dict, List
import os

from src.utils.logger import setup_logger
from src.utils.ssrf_protection import validate_confluence_url
from src.utils.rate_limiter import get_confluence_rate_limiter
from src.utils.security_logging import SecurityLogger

logger = setup_logger(__name__)


class ConfluenceParser:
    """
    Парсит требования из Confluence
    """

    def __init__(self):
        # Validate Confluence URL before connecting
        confluence_url = os.getenv('CONFLUENCE_URL')
        if confluence_url:
            is_valid, error = validate_confluence_url(confluence_url)
            if not is_valid:
                logger.error(f"Invalid Confluence URL: {error}")
                raise ValueError(f"Invalid Confluence URL: {error}")
        
        self.confluence = Confluence(
            url=confluence_url,
            username=os.getenv('CONFLUENCE_USER'),
            password=os.getenv('CONFLUENCE_TOKEN')
        )
        
        # Get rate limiter for API calls
        self.rate_limiter = get_confluence_rate_limiter()

    def get_page_content(self, page_id: str) -> Dict:
        """
        Получает content страницы Confluence с защитой от SSRF и rate limiting.
        """
        logger.info(f"Получение контента страницы {page_id}")
        
        # Rate limiting
        if not self.rate_limiter.allow_request():
            error_msg = f"Rate limit exceeded for Confluence API"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        try:
            page = self.confluence.get_page_by_id(
                page_id=page_id,
                expand='body.storage'
            )
        except Exception as e:
            logger.error(f"Ошибка при получении страницы {page_id}: {e}")
            SecurityLogger.log_auth_failure('confluence', str(e))
            raise

        return {
            'title': page['title'],
            'content': self._clean_html(page['body']['storage']['value']),
            'url': f"{os.getenv('CONFLUENCE_URL')}/pages/{page_id}"
        }

    def _clean_html(self, html: str) -> str:
        """
        Очищает HTML от тегов, оставляет текст
        """
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        return soup.get_text(separator='\n', strip=True)

    def extract_requirements(self, content: str) -> List[str]:
        """
        Извлекает отдельные требования из текста
        Простая логика: split по headers или нумерации
        """
        # Для MVP: split по двойным переносам
        # В Phase 2: более умная логика
        requirements = [
            req.strip()
            for req in content.split('\n\n')
            if len(req.strip()) > 50  # Минимальная длина
        ]
        return requirements


# Example usage:
if __name__ == "__main__":
    parser = ConfluenceParser()
    page = parser.get_page_content("123456")  # page ID
    logger.info(f"Title: {page['title']}")
    logger.info(f"Requirements: {len(parser.extract_requirements(page['content']))}")