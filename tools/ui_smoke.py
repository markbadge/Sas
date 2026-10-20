"""Drive the play client in headless Chromium against a stub-bot server: plays a full game, checks for horizontal scroll.
Usage: python3 tools/ui_smoke.py [port] [screenshot_dir]"""
import os
import subprocess
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
shots = sys.argv[2] if len(sys.argv) > 2 else None
store = tempfile.mkdtemp()
srv = subprocess.Popen([sys.executable, '-m', 'ssengine', 'serve', '--bots', 'stub', '--port', str(port), '--store', store],
                       cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
time.sleep(1.5)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path='/opt/pw-browsers/chromium')
        pg = b.new_page(viewport={'width': 390, 'height': 800})
        errs = []
        pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto(f'http://127.0.0.1:{port}/')
        pg.select_option('#lbots', 'stub')
        pg.fill('#lseed', '7')
        pg.click('text=New game')
        pg.wait_for_selector('text=Round 1 of 7')
        steps = 0
        while pg.locator('text=Final result').count() == 0 and steps < 60:
            steps += 1
            if pg.locator('#say').count():
                pg.fill('#say', f'hello from the human, step {steps}')
                pg.click('button:has-text("Submit")')
            elif pg.locator('.hand .card').count():
                pg.locator('.hand .card').first.click()
                if pg.locator('#target').count():
                    pg.select_option('#target', index=1)
                if shots and steps == 4:
                    pg.screenshot(path=os.path.join(shots, 'act_mobile.png'), full_page=True)
                pg.click('button:has-text("Submit")')
            else:
                time.sleep(0.4)
                continue
            time.sleep(0.6)
            sw, cw = pg.evaluate('[document.documentElement.scrollWidth, document.documentElement.clientWidth]')
            assert sw <= cw, f'horizontal scroll: {sw} > {cw}'
        assert pg.locator('text=Final result').count() == 1, 'game did not finish'
        if shots:
            pg.screenshot(path=os.path.join(shots, 'summary_mobile.png'), full_page=True)
        assert not errs, errs
        print('ui smoke ok after', steps, 'steps')
        b.close()
finally:
    srv.terminate()
