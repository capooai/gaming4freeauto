#!/usr/bin/python3.12
"""
G4F Multi-Server Renew — CloakBrowser 版
v6 - 修复：等待 Turnstile 验证模态框关闭后再检测结果
"""
import sys, re, time
from cloakbrowser import launch

SERVERS = [
    {"url": "https://g4f.gg/deku", "name": "Deku"},
    {"url": "https://g4f.gg/rena", "name": "Rena"},
]

def _parse_time(s):
    if s == 'N/A' or not s: return None
    try:
        parts = s.strip().split(':')
        if len(parts) == 3: return int(parts[0])*3600 + int(parts[1])*60 + int(parts[2])
        elif len(parts) == 2: return int(parts[0])*60 + int(parts[1])
        return None
    except: return None

def _run_single_attempt(url, name):
    browser = launch(headless=True, humanize=True)
    try:
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(4000)

        body = page.evaluate("document.body?.innerText || ''")
        if "Come back in" in body:
            return False, f"⏳ {name} 冷却中", None

        m = re.search(r'SERVER TIME REMAINING\s*([\d:]+)', body, re.I)
        before_str = m.group(1) if m else 'N/A'
        before_secs = _parse_time(before_str)
        print(f"[{name}] Before: {before_str}", file=sys.stderr)

        # 填写投票者名字
        page.wait_for_selector('input[name="voter_name"]', timeout=10000)
        page.fill('input[name="voter_name"]', 'Rena')

        # 清空 captcha 残留
        page.evaluate("window._captchaWidgetId = null; window._captchaPendingForm = null;")

        # 点击投票按钮（弹出 Turnstile 验证模态框）
        page.wait_for_selector('button.vote-btn', timeout=5000)
        page.evaluate("""() => {
            document.querySelector('button.vote-btn')?.click();
        }""")
        print(f"[{name}] Clicked vote button. Waiting for Turnstile...", file=sys.stderr)

        # 等待 captcha 模态框关闭（最多 40 秒）
        for i in range(20):
            page.wait_for_timeout(2000)
            try:
                display = page.evaluate(
                    "document.getElementById('captcha-modal')?.style?.display"
                )
                if display != 'flex':
                    print(f"[{name}] Modal closed at tick {i}", file=sys.stderr)
                    break
            except Exception:
                # 导航说明成功
                page.wait_for_timeout(3000)
                return True, f"✅ {name} 投票已提交（页面跳转）", "N/A"

        # 等待结果稳定
        page.wait_for_timeout(5000)

        # 读取结果
        result = page.evaluate("document.body?.innerText || ''")
        m2 = re.search(r'SERVER TIME REMAINING\s*([\d:]+)', result, re.I)
        after_str = m2.group(1) if m2 else 'N/A'
        after_secs = _parse_time(after_str)
        print(f"[{name}] After: {after_str}", file=sys.stderr)
        lower = result.lower()

        if "✓" in result and ("added" in lower or "minute" in lower):
            return True, f"✅ {name} 续期成功！剩余: {after_str}", after_str
        if before_secs and after_secs and after_secs > before_secs + 3000:
            diff = (after_secs - before_secs) // 60
            return True, f"✅ {name} 续期成功！剩余: {after_str} (+{diff}分)", after_str
        if "come back" in lower or "cooldown" in lower:
            return False, f"⏳ {name} 冷却中（{after_str}）", after_str
        return False, f"❌ {name} 未生效。剩余: {after_str}", after_str
    finally:
        try: browser.close()
        except: pass

def renew_server(url, name):
    for attempt in range(2):
        try:
            success, msg, tl = _run_single_attempt(url, name)
            if success or "冷却中" in msg:
                return success, msg, tl
            print(f"[{name}] 重试 #{attempt+1}...", file=sys.stderr)
        except Exception as e:
            print(f"[{name}] 异常: {e}", file=sys.stderr)
            if attempt == 1: return False, f"❌ {name} 错误: {e}", None
        if attempt < 1: time.sleep(3)
    return False, f"❌ {name} 续期失败", None

def main():
    results = []
    for s in SERVERS:
        print(f"\n=== {s['name']} ===", file=sys.stderr)
        ok, msg, tl = renew_server(s["url"], s["name"])
        results.append((ok, msg, tl))
    print("\n" + "="*30)
    print("📊 G4F 服务器续期报告")
    for _, msg, _ in results: print(f"  {msg}")

if __name__ == "__main__":
    main()
