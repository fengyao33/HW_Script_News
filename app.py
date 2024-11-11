import bs4
from flask import Flask, request, jsonify, render_template
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote
import random
import concurrent.futures
import os
import sqlite3
import time
import tldextract


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


# 存储所有的新闻项目
all_filtered_results = []
# 总页数
total_pages = 8


def clean_url(url):
    """解码URL编码并移除不必要的查询参数"""
    decoded_url = unquote(url)
    cleaned_url = re.sub(r'&.*$', '', decoded_url)
    return cleaned_url

def get_domain_name(url):
    domain = tldextract.extract(url).domain  
    domain_name_mapping = {
        'tw': '[奇摩新聞]',   
        'google': '[Google新聞]',
        'apple': '[蘋果新聞]',
        'cnn': '[CNN]',
    }
    return domain_name_mapping.get(domain, f'[{domain}新聞]')

def fetch_page_data(page, keyword):
    search_url = f"https://www.google.com/search?q={keyword}&tbm=nws"
    page_url = f"{search_url}&start={page * 10}"
    max_retries = 3  # 设置最大重试次数
    retry_delay = 5  # 设置重试的等待时间（秒）

    for attempt in range(max_retries):
        try:
            response = session.get(page_url)
            # 檢查429錯誤
            if response.status_code == 429:
                print("429 Too Many Requests...")
                time.sleep(retry_delay)  #
                continue
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
                    '下一頁' in aria_label or
                        not (link.startswith("http://") or link.startswith("https://"))):
                    continue

                title = item.get_text(strip=True)
                print(title)

                if not title or title in seen_titles:
                    continue

                seen_titles.add(title)
                article_url = clean_url(link)
                article_content = fetch_article_content(article_url)

                domain_name = get_domain_name(article_url)

                articles.append({
                    'domain': domain_name,
                    'title': title,
                    'link': clean_url(link),
                    'content': article_content
                })

            store_news_to_db(articles, keyword)
            return articles

        except requests.exceptions.RequestException as e:
            print(f"请求失败，错误信息: {e}")
            if attempt == max_retries - 1:  # 如果是最后一次重试
                return []

    return []


def create_database():
    conn = sqlite3.connect('news.db')  # 创建或连接到 SQLite 数据库
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS news (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        link TEXT,
                        keyword TEXT,
                        content TEXT,  -- 添加 content 字段
                        fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()


create_database()


def store_news_to_db(articles, keyword):
    """将新闻存入数据库"""
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()

    for article in articles:
        cursor.execute('''INSERT INTO news (title, link, keyword, content) 
                          VALUES (?, ?, ?, ?)''',
                       (article['title'], article['link'], keyword, article['content']))

    conn.commit()
    conn.close()


def fetch_article_content(url):
    try:
        response = session.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        paragraphs = soup.find_all('p')
        # content = "\n".join([p.get_text(strip=True) for p in paragraphs])
        content = "\n".join([p.get_text(strip=True)
                            for p in paragraphs if isinstance(p, bs4.element.Tag)])
        return content
    except requests.exceptions.RequestException as e:
        print(f"獲取內容失敗: {e}")
        return "Failed to retrieve content"


@app.route('/')
def index():
    return render_template('index.html') 

@app.route('/scrape', methods=['GET'])
def scrape():
    keyword = request.args.get('keyword', default='台積電', type=str)  
    try:
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
        print(f"發生錯誤: {e}")  # 打印错误到控制台
        return jsonify({'error': str(e)}), 500


@app.route('/get_news', methods=['GET'])
def get_news():
    keyword = request.args.get('keyword', default='', type=str) 
    conn = sqlite3.connect('news.db')
    cursor = conn.cursor()

    if keyword:
        cursor.execute('''SELECT title, link, keyword, fetched_at 
                          FROM news WHERE keyword LIKE ? ORDER BY fetched_at DESC''', ('%' + keyword + '%',))
    else:
        cursor.execute(
            '''SELECT title, link, keyword, fetched_at FROM news ORDER BY fetched_at DESC''')

    rows = cursor.fetchall()
    conn.close()

    news_items = [{'title': row[0], 'link': row[1],
                   'keyword': row[2], 'fetched_at': row[3]} for row in rows]

    print(news_items)
    return jsonify(news_items)


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv("PORT", default=5000), host='0.0.0.0')
