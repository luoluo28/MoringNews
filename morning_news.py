#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
import feedparser
import json
import time
import os
from datetime import datetime

# ================= 从环境变量读取密钥 =================
CORP_ID = os.environ.get("CORP_ID")
AGENT_ID = os.environ.get("AGENT_ID")
SECRET = os.environ.get("SECRET")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

# ================= RSS 源配置 =================
NEWS_FEEDS = [
    "https://www.36kr.com/feed",
    "https://feed.ithome.com/",
    "https://rsshub.app/xueqiu/stock/market",
]
MAX_ITEMS = 12

def get_access_token():
    url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={CORP_ID}&corpsecret={SECRET}"
    resp = requests.get(url, timeout=10)
    data = resp.json()
    if data.get("errcode") == 0:
        return data["access_token"]
    else:
        raise Exception(f"获取token失败: {data}")

def fetch_news():
    articles = []
    for feed_url in NEWS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:5]:
                title = entry.get('title', '')
                link = entry.get('link', '')
                if title and link:
                    articles.append({"title": title, "link": link})
        except Exception as e:
            print(f"抓取失败 {feed_url}: {e}")
        time.sleep(1)
    seen = set()
    unique = []
    for a in articles:
        if a['title'] not in seen:
            seen.add(a['title'])
            unique.append(a)
    return unique[:MAX_ITEMS]

def summarize_by_deepseek(articles):
    news_text = "\n".join([f"- {a['title']}" for a in articles])
    prompt = f"""请根据以下新闻标题，生成一份今天的早报。要求：
1. 选择最重要的5-8条新闻
2. 每条新闻用一句话概括，不超过30字
3. 按“要闻”“财经”“科技”分类（没有的分类可不写）
4. 最后加上一句今日天气提示（北京，多云18-26℃）
5. 输出格式简洁，不要多余解释

新闻列表：
{news_text}
"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.5,
        "max_tokens": 800
    }
    resp = requests.post("https://api.deepseek.com/v1/chat/completions", 
                         json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    return result["choices"][0]["message"]["content"]

def main():
    print("开始抓取新闻...")
    articles = fetch_news()
    print(f"抓取到 {len(articles)} 条")
    if not articles:
        # 推送失败提示（简化处理）
        print("没有抓取到新闻")
        return

    print("调用DeepSeek...")
    summary = summarize_by_deepseek(articles)

    # 构造原文链接部分（markdown格式，支持可点击链接）
    link_section = "\n\n---\n📎 原文链接：\n"
    for a in articles[:6]:
        link_section += f"[{a['title'][:20]}]({a['link']})\n"
    final_content = summary + link_section

    access_token = get_access_token()
    url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
    data = {
        "touser": "@all",
        "msgtype": "markdown",
        "agentid": int(AGENT_ID),
        "markdown": {
            "content": final_content
        }
    }
    resp = requests.post(url, json=data, timeout=10)
    print("推送结果:", resp.json())

if __name__ == "__main__":
    main()