import os
import csv
import time
import random
import json
import argparse
import logging
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# ---------- 配置日志 ----------
logging.basicConfig(
    filename="scraper_v2.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
console.setFormatter(formatter)
logging.getLogger().addHandler(console)


# ---------- Driver 管理 ----------
def get_driver(domain, headless=False, user_agent=None, window_size="1920,1080", page_load_timeout=25):
    """返回配置好的 Selenium Chrome driver，默认非 headless 模式"""
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")  # 如需无头模式可开启
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(f"--window-size={window_size}")
    # 随机User-Agent
    if user_agent is None:
        user_agent = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141 Safari/537.36")
    chrome_options.add_argument(f"user-agent={user_agent}")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    driver.set_page_load_timeout(page_load_timeout)

    # 隐藏自动化标识
    try:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.navigator.chrome = {runtime: {}};
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            """
        })
    except Exception:
        pass

    # 初始化访问域名主页
    try:
        driver.get(domain)
    except Exception:
        pass

    return driver


# ---------- Cookies 管理 ----------
def save_cookies(driver, cookies_path="cookies.json"):
    cookies = driver.get_cookies()
    with open(cookies_path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    logging.info(f"Cookies 已保存到 {cookies_path}")


def load_cookies(driver, domain, cookies_path="cookies.json"):
    """加载已有cookies，模拟登录状态"""
    if not os.path.exists(cookies_path):
        return False
    with open(cookies_path, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    try:
        driver.get(domain)
    except Exception:
        pass
    for c in cookies:
        cookie = {k: v for k, v in c.items() if k in ("name", "value", "path", "domain", "secure", "httpOnly", "expiry")}
        try:
            driver.add_cookie(cookie)
        except Exception:
            continue
    logging.info(f"已加载 {len(cookies)} 个cookies")
    return True


# ---------- 页面行为模拟 ----------
def human_scroll(driver, duration=3.0):
    """模拟人类滚动行为（延长滚动时间，确保描述区域加载）"""
    try:
        end_time = time.time() + duration
        viewport_height = driver.execute_script("return window.innerHeight")
        while time.time() < end_time:
            scroll_amount = random.randint(int(viewport_height * 0.2), int(viewport_height * 0.8))
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(0.3, 0.9))
    except Exception:
        pass
    try:
        # 滚动到描述区域附近，确保加载完全
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight * 0.3);")
        time.sleep(1.0)
    except Exception:
        pass


# ---------- 视频提取函数 ----------
def extract_videos_and_descriptions(soup):
    """提取页面中的MP4视频URL和对应的视频描述"""
    videos = []
    video_descriptions = []
    
    # 1. 从视频播放器标签提取
    video_tags = soup.find_all("video")
    for video in video_tags:
        src = video.get("src")
        if src and src.endswith(".mp4") and src not in videos:
            videos.append(src)
            # 尝试获取视频描述（通常在视频附近的文字说明）
            desc_elem = video.find_next("p", class_="a-size-base") or video.find_parent().find("span", class_="a-text-normal")
            video_descriptions.append(desc_elem.get_text(strip=True) if desc_elem else "")
    
    # 2. 从脚本标签中的JSON数据提取（部分视频URL藏在JS里）
    script_tags = soup.find_all("script", type="text/javascript")
    for script in script_tags:
        script_text = script.get_text()
        if "videoUrl" in script_text or ".mp4" in script_text:
            # 简单提取MP4链接（处理JSON格式的视频URL）
            import re
            mp4_urls = re.findall(r'https?://[^\s"]+\.mp4', script_text)
            for url in mp4_urls:
                if url not in videos:
                    videos.append(url)
                    # 脚本中的视频描述较难匹配，默认留空或标记为"脚本提取视频"
                    video_descriptions.append("Script-extracted video")
    
    # 3. 从缩略图区域提取视频（带播放按钮的视频）
    video_thumbnails = soup.select("div[data-feature-name='video-thumbnails'] img")
    for thumb in video_thumbnails:
        # 从缩略图父元素找视频链接
        video_parent = thumb.find_parent("a", href=True)
        if video_parent:
            # 部分视频页链接格式：/video/product-video/B0XXXXXXX
            video_page_url = video_parent["href"]
            if "/video/" in video_page_url:
                # 拼接完整URL（实际视频可能需要进一步请求，这里简化处理）
                full_url = f"https://www.amazon.com{video_page_url}" if video_page_url.startswith("/") else video_page_url
                if full_url not in videos:
                    videos.append(full_url)
                    # 提取视频标题作为描述
                    video_title = thumb.get("alt", "").strip()
                    video_descriptions.append(video_title if video_title else "Video thumbnail")
    
    return videos, video_descriptions


# ---------- HTML 解析器（整合所有需求） ----------
def parse_product_page(html, url):
    soup = BeautifulSoup(html, "html.parser")
    front_data = {"URL": url}

    # 标题
    title_elem = soup.find("span", id="productTitle")
    front_data["Title"] = title_elem.get_text(strip=True) if title_elem else ""

    # 仅保留标价（List Price，不包含现价）
    list_price_elem = soup.find("span", class_="a-text-strike")
    front_data["List Price"] = list_price_elem.get_text(strip=True) if list_price_elem else ""

    # 评分
    rating_elem = soup.find("span", {"data-hook": "rating-out-of-text"})
    front_data["Rating"] = rating_elem.get_text(strip=True) if rating_elem else ""

    # 评论数
    review_elem = soup.find("span", id="acrCustomerReviewText")
    front_data["ReviewCount"] = review_elem.get_text(strip=True) if review_elem else ""

    # 品牌
    brand_elem = soup.find("a", id="bylineInfo") or soup.find("span", {"data-hook": "product-brand"})
    if brand_elem:
        front_data["Brand"] = brand_elem.get_text(strip=True).replace("Visit the ", "").replace(" Store", "")
    else:
        front_data["Brand"] = ""

    # 商品图片
    images = []
    img_tags = soup.select("#altImages img") or soup.select("img.a-dynamic-image")
    for img in img_tags:
        src = img.get("src")
        if src and "sprite" not in src and src not in images:
            if "_AC_" in src:
                images.append(src.split("_AC_")[0] + "_SL1500_.jpg")
            else:
                images.append(src)
    for i, img_url in enumerate(images):
        front_data[f"Image{i+1}"] = img_url

    # 提取视频和视频描述（新增功能）
    videos, video_descriptions = extract_videos_and_descriptions(soup)
    for i, (video_url, desc) in enumerate(zip(videos, video_descriptions)):
        front_data[f"Video{i+1}_URL"] = video_url  # 视频URL（MP4）
        front_data[f"Video{i+1}_Description"] = desc  # 视频描述

    # 扩展信息存储
    ext_data = {}

    # 1. 五点信息（Bullet Points）
    feature_bullets = soup.find("div", id="feature-bullets")
    if feature_bullets:
        bullets = []
        for li in feature_bullets.find_all("li"):
            text = li.get_text(strip=True)
            if text:
                bullets.append(text)
        # 按顺序存储为 Bullet1 - Bullet5（或更多）
        for i, bullet in enumerate(bullets, 1):
            ext_data[f"Bullet{i}"] = bullet

    # 2. 产品描述（Product description，仅文字，过滤图片）
    product_desc_section = soup.find("div", id="productDescription")
    if product_desc_section:
        # 清除所有图片标签，只保留文字
        for img in product_desc_section.find_all("img"):
            img.decompose()  # 移除图片标签
        desc_text = product_desc_section.get_text(separator="\n", strip=True)
        # 清理多余空行和空格
        desc_text = "\n".join([line.strip() for line in desc_text.splitlines() if line.strip()])
        ext_data["Product Description"] = desc_text

    # 3. 其他产品规格信息
    detail_bullets = soup.find("div", id="detailBullets_feature_div")
    if detail_bullets:
        for li in detail_bullets.find_all("li"):
            text = li.get_text(separator=" ", strip=True)
            if ":" in text:
                parts = text.split(":", 1)
                ext_data[parts[0].strip()] = parts[1].strip()

    info_section = soup.find("div", id="prodDetails") or soup.find("div", id="productDetails_detailBullets_sections1")
    if not info_section:
        info_section = soup.find("div", {"data-feature-name": "productOverview_feature_div"})
    if info_section:
        for row in info_section.find_all(["tr", "li"]):
            th = row.find("th") or row.find("span", class_="a-text-bold")
            td = row.find("td") or row.find("span", class_="a-text-normal")
            if th and td:
                key = th.get_text(strip=True).replace(":", "")
                value = td.get_text(strip=True)
                ext_data[key] = value

    tech = soup.find("table", id="productDetails_techSpec_section_1")
    if tech:
        for tr in tech.find_all("tr"):
            tds = tr.find_all("td")
            th = tr.find("th")
            if th and tds:
                key = th.get_text(strip=True)
                value = tds[0].get_text(strip=True)
                ext_data[key] = value

    features_sections = soup.find_all("div", class_="a-section a-spacing-none po-expand-content")
    for section in features_sections:
        key_elem = section.find("span", class_="a-text-bold")
        val_elem = section.find("span", class_="a-text-normal")
        if key_elem and val_elem:
            key = key_elem.get_text(strip=True).replace(":", "")
            val = val_elem.get_text(strip=True)
            ext_data[key] = val

    # 合并数据并清理格式
    data = {**front_data, **ext_data}
    for k, v in list(data.items()):
        if isinstance(v, str):
            data[k] = " ".join(v.split())  # 统一处理空格和换行
    return data


# ---------- 验证码/反爬检测 ----------
def is_robot_page(html):
    """检测是否触发验证码或反爬页面"""
    if not html:
        return True
    lower = html.lower()
    checks = [
        "enter the characters you see below", "robot check", "type the characters you see", 
        "sorry, we just need to make sure", "press and hold", "are you a robot", 
        "detected unusual traffic", "to discuss automated access to amazon services"
    ]
    for c in checks:
        if c in lower:
            return True
    if len(html) < 2000:
        if "producttitle" not in lower and "product title" not in lower and "add to cart" not in lower:
            return True
    return False


# ---------- 单 ASIN 抓取（带重试） ----------
def scrape_asin(asin, domain, driver, retries=2, wait_after_load=(2.0, 4.0)):
    url = f"{domain.rstrip('/')}/dp/{asin}"
    attempt = 0
    while attempt <= retries:
        attempt += 1
        try:
            logging.info(f"抓取 {asin}（第 {attempt}/{retries+1} 次尝试）-> {url}")
            driver.get(url)
            time.sleep(random.uniform(*wait_after_load))  # 等待页面主框架加载
            human_scroll(driver, duration=random.uniform(2.5, 4.0))  # 延长滚动，确保视频和描述加载
            
            # 额外等待视频加载（新增）
            time.sleep(random.uniform(1.5, 2.5))
            html = driver.page_source

            if is_robot_page(html):
                logging.warning(f"{asin} 触发验证码/反爬，第 {attempt} 次尝试失败")
                if attempt <= retries:
                    sleep_time = random.uniform(5, 12)
                    logging.info(f"休眠 {sleep_time:.1f} 秒后重试...")
                    time.sleep(sleep_time)
                    continue
                else:
                    return {"ASIN": asin, "URL": url, "Error": "触发验证码/反爬检测"}
            
            data = parse_product_page(html, url)
            data["ASIN"] = asin
            logging.info(f"{asin} 抓取成功")
            return data
        except TimeoutException as e:
            logging.warning(f"{asin} 超时: {e}")
            if attempt <= retries:
                time.sleep(3 + attempt)
                continue
            return {"ASIN": asin, "URL": url, "Error": f"超时: {e}"}
        except WebDriverException as e:
            logging.error(f"{asin} 浏览器异常: {e}")
            return {"ASIN": asin, "URL": url, "Error": f"浏览器异常: {e}"}
        except Exception as e:
            logging.exception(f"{asin} 未知错误: {e}")
            if attempt <= retries:
                time.sleep(2 + attempt)
                continue
            return {"ASIN": asin, "URL": url, "Error": str(e)}
    return {"ASIN": asin, "URL": url, "Error": "未知错误"}


# ---------- 保存结果 ----------
def save_results(results, csv_path, json_path=None):
    """保存CSV和可选JSON结果，确保字段顺序合理"""
    all_keys = []
    # 核心字段优先
    front_keys = ["ASIN", "URL", "Title", "Brand", "List Price", "Rating", "ReviewCount"]
    for key in front_keys:
        if any(key in r for r in results):
            all_keys.append(key)
    
    # 图片字段排序
    img_keys = []
    for r in results:
        for k in r.keys():
            if k.startswith("Image") and k not in img_keys:
                img_keys.append(k)
    try:
        img_keys.sort(key=lambda x: int(x.replace("Image", "")))
    except Exception:
        img_keys.sort()
    all_keys.extend(img_keys)
    
    # 视频字段排序（新增）
    video_url_keys = []
    video_desc_keys = []
    for r in results:
        for k in r.keys():
            if k.endswith("_URL") and k.startswith("Video") and k not in video_url_keys:
                video_url_keys.append(k)
            if k.endswith("_Description") and k.startswith("Video") and k not in video_desc_keys:
                video_desc_keys.append(k)
    try:
        video_url_keys.sort(key=lambda x: int(x.replace("Video", "").split("_")[0]))
        video_desc_keys.sort(key=lambda x: int(x.replace("Video", "").split("_")[0]))
    except Exception:
        video_url_keys.sort()
        video_desc_keys.sort()
    all_keys.extend(video_url_keys)
    all_keys.extend(video_desc_keys)
    
    # 五点信息字段（Bullet1, Bullet2...）
    bullet_keys = []
    for r in results:
        for k in r.keys():
            if k.startswith("Bullet") and k not in bullet_keys:
                bullet_keys.append(k)
    try:
        bullet_keys.sort(key=lambda x: int(x.replace("Bullet", "")))
    except Exception:
        bullet_keys.sort()
    all_keys.extend(bullet_keys)

    # 产品描述字段
    if any("Product Description" in r for r in results):
        all_keys.append("Product Description")
    
    # 其他扩展字段
    for r in results:
        for key in r.keys():
            if key not in all_keys and not key.startswith(("Image", "Bullet", "Video")):
                all_keys.append(key)

    # 写入CSV
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(results)
    logging.info(f"CSV结果已保存至 {csv_path}")

    # 写入JSON（可选）
    if json_path:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logging.info(f"JSON结果已保存至 {json_path}")


# ---------- 主流程 ----------
def main():
    parser = argparse.ArgumentParser(description="Amazon ASIN Scraper - 抓取标价、五点信息、产品描述及视频")
    parser.add_argument("--domain", default="https://www.amazon.com", help="亚马逊域名（如 https://www.amazon.co.uk）")
    parser.add_argument("--in", dest="input_file", default="asins.txt", help="输入ASIN文件（默认 asins.txt）")
    parser.add_argument("--out-csv", default="output.csv", help="输出CSV文件（默认 output.csv）")
    parser.add_argument("--out-json", default=None, help="输出JSON文件（可选）")
    parser.add_argument("--batch-size", type=int, default=10, help="每批抓取数量（默认 10）")
    parser.add_argument("--batch-delay", type=int, default=60, help="批间间隔秒数（默认 60）")
    parser.add_argument("--cookies", default="cookies.json", help="Cookies文件路径（默认 cookies.json）")
    parser.add_argument("--headless", action="store_true", help="无头模式运行（不推荐）")
    parser.add_argument("--retries", type=int, default=2, help="失败重试次数（默认 2）")
    args = parser.parse_args()

    input_file = args.input_file
    if not os.path.exists(input_file):
        logging.error(f"未找到输入文件 {input_file}")
        return

    # 读取ASIN列表
    with open(input_file, "r", encoding="utf-8") as f:
        all_asins = [line.strip() for line in f if line.strip()]
    total = len(all_asins)
    logging.info(f"共发现 {total} 个ASIN，将按每批 {args.batch_size} 个处理")

    # 初始化浏览器
    driver = get_driver(args.domain, headless=args.headless)
    cookies_loaded = False
    if os.path.exists(args.cookies):
        try:
            cookies_loaded = load_cookies(driver, args.domain, cookies_path=args.cookies)
            driver.get(args.domain)
            time.sleep(1.0)
            logging.info("已加载cookies并验证登录态")
        except Exception as e:
            logging.warning(f"加载cookies失败: {e}")
            cookies_loaded = False

    # 首次运行需手动登录并保存cookies
    if not cookies_loaded:
        print("\n⚠️ 未检测到可用cookies，请在打开的浏览器中手动登录亚马逊")
        print("登录后确认可访问商品页，再回到控制台按回车继续")
        input("登录完成后按 Enter 继续...")
        try:
            save_cookies(driver, cookies_path=args.cookies)
        except Exception as e:
            logging.warning(f"保存cookies失败: {e}")

    results = []
    # 断点续爬：跳过已抓取的ASIN
    seen_asins = set()
    if os.path.exists(args.out_csv):
        try:
            with open(args.out_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if "ASIN" in row and row["ASIN"]:
                        seen_asins.add(row["ASIN"])
            logging.info(f"已抓取 {len(seen_asins)} 个ASIN，将跳过这些进行续爬")
        except Exception:
            pass

    # 分批抓取
    try:
        for i in range(0, total, args.batch_size):
            batch_asins = [a for a in all_asins[i:i + args.batch_size] if a not in seen_asins]
            if not batch_asins:
                logging.info(f"第 {(i // args.batch_size) + 1} 批无未抓取ASIN，跳过")
                continue

            batch_num = (i // args.batch_size) + 1
            logging.info(f"开始处理第 {batch_num} 批（{len(batch_asins)} 个ASIN）")

            for asin in tqdm(batch_asins, desc=f"Batch {batch_num}"):
                data = scrape_asin(asin, args.domain, driver, retries=args.retries)
                results.append(data)
                # 实时保存进度，避免数据丢失
                try:
                    existing = []
                    if os.path.exists(args.out_csv):
                        with open(args.out_csv, "r", encoding="utf-8-sig") as f:
                            reader = csv.DictReader(f)
                            existing = [row for row in reader]
                    asin_to_row = {r.get("ASIN"): r for r in existing if r.get("ASIN")}
                    for r in results:
                        asin_to_row[r.get("ASIN")] = r
                    save_results(list(asin_to_row.values()), args.out_csv, args.out_json)
                except Exception as e:
                    logging.warning(f"实时保存失败: {e}")

                # 单ASIN间隔，降低反爬风险
                time.sleep(random.uniform(2.0, 5.0))

            # 批间休眠（随机化时间）
            if i + args.batch_size < total:
                delay = random.uniform(args.batch_delay * 0.8, args.batch_delay * 1.2)
                logging.info(f"第 {batch_num} 批完成，休眠 {int(delay)} 秒后继续...")
                time.sleep(delay)

    finally:
        try:
            driver.quit()
            logging.info("浏览器已关闭")
        except Exception:
            pass

    logging.info(f"全部完成！结果已保存至 {args.out_csv}")
    if args.out_json:
        logging.info(f"JSON结果已保存至 {args.out_json}")


if __name__ == "__main__":
    main()  