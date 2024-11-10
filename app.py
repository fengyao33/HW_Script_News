from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote
import random
import concurrent.futures
import os


app = Flask(__name__)

# 设置会话并更新头部
session = requests.Session()
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 9; Pixel 3 XL Build/PQ1A.190505.001) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edge/91.0.864.59",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Trident/7.0; AS; .NET CLR 4.0.30319; AS; MAS; rv:11.0) like Gecko",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.149 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; rv:34.0) Gecko/20100101 Firefox/34.0",
    "Mozilla/5.0 (Linux; Android 10; Pixel 4 XL Build/QD4A.190502.012) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.136 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:69.0) Gecko/20100101 Firefox/69.0",
    "Mozilla/5.0 (Linux; Android 8.0.0; Nexus 5X Build/OPD1.170816.012) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.98 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:48.0) Gecko/20100101 Firefox/48.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36",
]

session.headers.update({
    "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
    "Referer": "https://news.google.com/",
    "User-Agent": random.choice(user_agents),
})

keyword = '川普'
search_url = f"https://www.google.com/search?q={keyword}&tbm=nws"

# 存储所有的新闻项目
all_filtered_results = []
# 总页数
total_pages = 8


def clean_url(url):
    """解码URL编码并移除不必要的查询参数"""
    decoded_url = unquote(url)
    cleaned_url = re.sub(r'&.*$', '', decoded_url)
    return cleaned_url


def fetch_page_data(page, keyword):
    search_url = f"https://www.google.com/search?q={keyword}&tbm=nws"
    page_url = f"{search_url}&start={page * 10}"

    try:
        response = session.get(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        print(soup.prettify()[:500])  # 打印前500个字符，查看 HTML 是否正常

        seen_titles = set()
        articles = []

        for item in soup.select('a[href]'):
            link = item.get('href')
            aria_label = item.get('aria-label', '')

            if (link.startswith('/setprefs?') or
                link.startswith('/url?') or
                link.startswith('https://policies.google.com') or
                link.startswith('https://accounts.google.com') or
                link.startswith('https://maps.google.com') or
                link.startswith('https://www.google.com/') or
                link.startswith('http://www.google.com/') or
                link.startswith('https://support.google.com/') or
                link.startswith('/search?') or
                    '上一頁' in aria_label or
                    '下一頁' in aria_label):
                continue

            title = item.get_text(strip=True)

            if not title or title in seen_titles:
                continue

            seen_titles.add(title)
            articles.append({
                'title': title,
                'link': clean_url(link)
            })

        return articles

    except Exception as e:
        print(f"发生错误: {e}")
        return []


@app.route('/')
def index():
    return render_template('index.html')  # 返回SSR页面


@app.route('/scrape', methods=['GET'])
def scrape():
    keyword = request.args.get('keyword', default='川普', type=str)  # 获取请求中的关键词
    try:
        # 使用线程池来并行获取多个页面的数据
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(fetch_page_data, range(
                total_pages), [keyword]*total_pages))

        # 扁平化列表
        all_results = [item for sublist in results for item in sublist]

        # 去除重复标题
        unique_results = {item['title']: item for item in all_results}.values()

        # 返回 JSON 格式的数据
        return jsonify(list(unique_results))

    except Exception as e:
        print(f"发生错误: {e}")  # 打印错误到控制台
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000), host='0.0.0.0')
