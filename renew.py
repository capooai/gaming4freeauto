#!/usr/bin/python3.12
"""
G4F Multi-Server Renew — CloakBrowser 版
支持多个服务器续期，每服务器加 90 分钟
v3 - 修复浏览器泄漏漏洞，优化 Playwright 元素等待
"""
import sys
import re
import time
from cloakbrowser import launch

SERVERS = [
    {"url": "https://g4f.gg/deku", "name": "Deku"},
    {"url": "https://g4f.gg/rena", "name": "Rena"},
]

def _parse_time(s):
    """HH:MM:SS -> 秒数，失败返回 None"""
    if s == 'N/A' or not s:
        return None
    try:
        parts = s.strip().split(':')
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return None
    except:
        return None

def _run_single_attempt(url, name):
    """执行单次续期尝试，核心逻辑。确保异常能抛出供外层捕获"""
    browser = launch(headless=True, humanize=True)
    try:
        page = browser.new_page()
        # 延长超时时间到 45 秒，确保 Cloudflare 盾牌盾加载完成
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        
        # 稍等片刻让页面完全稳定
        page.wait_for_timeout(3000)

        body = page.evaluate("document.body?.innerText || ''")

        if "Come back in" in body:
            return False, f"⏳ {name} 冷却中", None

        # 匹配初始时间 (忽略大小写)
        m = re.search(r'SERVER TIME REMAINING\s*([\d:]+)', body, re.I)
        before_str = m.group(1) if m else 'N/A'
        before_secs = _parse_time(before_str)
        print(f"[{name}] Before: {before_str}", file=sys.stderr)

        # 确保输入框已经渲染
        page.wait_for_selector('input[name="voter_name"]', timeout=10000)
        page.fill('input[name="voter_name"]', 'Rena')

        # 确保按钮可以点击并点击
        page.wait_for_selector('button.vote-btn', timeout=5000)
        page.click('button.vote-btn')
        print(f"[{name}] Clicked vote button. Waiting for verification...", file=sys.stderr)

        # 关键：点击后，Turnstile 往往需要几秒钟隐式响应或弹出验证
        # 循环检测页面状态变化，最多等待 30 秒
        success_detected = False
        after_str = 'N/A'
        
        for _ in range(15):
            page.wait_for_timeout(2000)  # 每 2 秒轮询一次
            current_text = page.evaluate("document.body?.innerText || ''")
            lower_text = current_text.lower()
            
            # 1. 检查是否有成功标志
            if "✓" in current_text and ("added" in lower_text or "minute" in lower_text):
                success_detected = True
            
            # 2. 尝试提取最新的时间
            m2 = re.search(r'SERVER TIME REMAINING\s*([\d:]+)', current_text, re.I)
            if m2:
                after_str = m2.group(1)
                
            if success_detected:
                break
                
        after_secs = _parse_time(after_str)
        print(f"[{name}] After: {after_str}", file=sys.stderr)

        # 结果判定
        if success_detected:
            return True, f"✅ {name} 续期成功！剩余: {after_str}", after_str

        if before_secs and after_secs and after_secs > before_secs + 3000:
            diff_min = (after_secs - before_secs) // 60
            return True, f"✅ {name} 续期成功！剩余: {after_str} (+{diff_min}分)", after_str

        if "come back" in lower_text or "cooldown" in lower_text:
            return False, f"⏳ {name} 冷却中（{after_str}）", after_str

        return False, f"❌ {name} 续期未成功。剩余: {after_str}", after_str

    finally:
        # 无论成功还是抛出异常，单次交互完毕后必须关闭浏览器
        try:
            browser.close()
        except:
            pass

def renew_server(url, name):
    """带重试机制的包裹函数（无递归，安全释放资源）"""
    max_retries = 2
    for attempt in range(max_retries):
        try:
            success, msg, time_left = _run_single_attempt(url, name)
            
            # 如果成功，或者是确定处于冷却中，则无需重试
            if success or "冷却中" in msg:
                return success, msg, time_left
                
            print(f"[{name}] 尝试未成功，准备进行重试...", file=sys.stderr)
            
        except Exception as e:
            print(f"[{name}] 第 {attempt + 1} 次尝试发生异常: {e}", file=sys.stderr)
            if attempt == max_retries - 1:
                return False, f"❌ {name} 错误: {e}", None
                
        # 重试前等待 3 秒
        if attempt < max_retries - 1:
            time.sleep(3)
            
    return False, f"❌ {name} 续期失败（已重试）", None

def main():
    results = []
    for server in SERVERS:
        print(f"\n=== 开始续期服务器: {server['name']} ===", file=sys.stderr)
        success, msg, time_left = renew_server(server["url"], server["name"])
        results.append((success, msg, time_left))

    print("\n" + "="*30)
    print("📊 G4F 服务器续期报告")
    for _, msg, _ in results:
        print(f"  {msg}")
    print("="*30)
    sys.stderr.flush()

if __name__ == "__main__":
    main()
