import os  # <--- [修改1] 新增这行
import logging
from mcp.server.fastmcp import FastMCP
import httpx
import xml.etree.ElementTree as ET
from typing import Dict

# 1. 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 2. 初始化 MCP 服务
mcp = FastMCP("AcademicPaperResearcher")

# [之前修正的 HTTPS 地址，保持不用动]
ARXIV_API_URL = "https://export.arxiv.org/api/query"


def parse_arxiv_entry(entry) -> Dict:
    """解析 XML 辅助函数"""
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    try:
        title = entry.find('atom:title', ns).text.strip().replace('\n', ' ')
        summary = entry.find('atom:summary', ns).text.strip().replace('\n', ' ')
        published = entry.find('atom:published', ns).text.strip()
        authors = [author.find('atom:name', ns).text for author in entry.findall('atom:author', ns)]
        links = entry.findall('atom:link', ns)
        pdf_link = next((link.attrib['href'] for link in links if link.attrib.get('title') == 'pdf'), "No PDF found")
    except AttributeError:
        # 防止某个字段缺失导致报错
        return {"title": "Unknown", "authors": "", "published": "", "summary": "", "pdf_link": ""}

    return {
        "title": title,
        "authors": ", ".join(authors),
        "published": published,
        "summary": summary,
        "pdf_link": pdf_link
    }


@mcp.tool()
async def search_papers(query: str, max_results: int = 5) -> str:
    """
    根据关键词搜索最新学术论文 (ArXiv).
    Args:
        query: 搜索关键词 (如 "LLM", "Quantum Computing").
        max_results: 返回数量，默认 5.
    """
    logger.info(f"Received search request: query='{query}', max_results={max_results}")

    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(ARXIV_API_URL, params=params, timeout=15.0)
            response.raise_for_status()
        except Exception as e:
            error_msg = f"ArXiv API Error: {str(e)}"
            logger.error(error_msg)
            return error_msg

    try:
        root = ET.fromstring(response.text)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', ns)
    except Exception as e:
        return f"XML Parse Error: {str(e)}"

    if not entries:
        return "No papers found."

    formatted_output = [f"Found {len(entries)} papers for '{query}':\n"]
    for i, entry in enumerate(entries, 1):
        data = parse_arxiv_entry(entry)
        formatted_output.append(
            f"--- Paper {i} ---\n"
            f"Title: {data['title']}\n"
            f"Authors: {data['authors']}\n"
            f"Date: {data['published'][:10]}\n"
            f"PDF: {data['pdf_link']}\n"
            f"Abstract: {data['summary'][:500]}...\n"
        )

    return "\n".join(formatted_output)


# --- [修改2] 下面是针对云部署的核心修改 ---
if __name__ == "__main__":
    # 获取 Render/Railway 等平台提供的端口，如果没有则默认 8000
    port = int(os.getenv("PORT", 8000))

    print(f"Starting MCP Server on 0.0.0.0:{port}")

    # 关键参数：
    # host="0.0.0.0" 表示允许外部（公网）访问
    # port=port 使用云平台指定的端口
    mcp.run(transport="sse", host="0.0.0.0", port=port)

