"""Real browser smoke checks. Requires optional playwright; uses installed Edge."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8000')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'url': args.url,
              'method': 'Playwright / local Edge headless; real service except explicit HTTP error fixture',
              'checks': [], 'responses': [], 'page_errors': [], 'human_confirmation': 'pending'}
    def check(name):
        report['checks'].append({'name': name, 'passed': True})
    def save():
        report['artifacts'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in args.output.iterdir() if p.name != 'browser.json'}
        (args.output / 'browser.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            report['browser_version'] = browser.version
            context = browser.new_context(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
            page = context.new_page()
            page.on('pageerror', lambda error: report['page_errors'].append(str(error)))
            page.goto(args.url)
            expect(page.locator('#connection')).to_have_text('知识库已连接')
            expect(page.locator('#welcome')).to_be_visible()
            page.screenshot(path=str(args.output / '01-welcome.png'), full_page=True)
            check('desktop page and real service health')

            def ask(question, status, index, hold=False):
                page.locator('#question').fill(question)
                pending = []
                if hold:
                    page.route('**/api/chat', lambda route: pending.append(route))
                with page.expect_response(lambda r: r.url.endswith('/api/chat') and r.request.method == 'POST', timeout=200000) as response:
                    page.locator('#send').click()
                    if hold:
                        page.wait_for_function("document.querySelector('.pending') !== null")
                        expect(page.locator('#send')).to_be_disabled()
                        expect(page.locator('#new-chat')).to_be_disabled()
                        expect(page.locator('#question')).to_be_disabled()
                        expect(page.locator('.pending')).to_have_text('正在查阅企业知识库…')
                        page.screenshot(path=str(args.output / '02-waiting.png'), full_page=True)
                        # A second submit event must not produce a second request.
                        page.locator('#question-form').dispatch_event('submit')
                        page.wait_for_timeout(100)
                        assert len(pending) == 1
                        check('waiting state and duplicate submit guard')
                        pending[0].continue_()
                        page.unroute('**/api/chat')
                raw = response.value
                assert raw.status == 200
                payload = raw.json()
                (args.output / f'{index}-response.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
                result = payload['result']
                assert result['status'] == status, result['answer']
                expect(page.locator('#send')).to_be_enabled(timeout=10000)
                box = page.locator('.assistant-message').last
                expect(box.locator('.answer')).to_have_text(result['answer'])
                expect(box.locator('.citation')).to_have_count(len(result['citations']))
                for n, citation in enumerate(result['citations']):
                    expect(box.locator('.citation').nth(n)).to_contain_text(citation['quote'])
                    expect(box.locator('.citation').nth(n)).to_contain_text(citation['chunk_id'])
                assert box.locator('.gap').count() == bool(result['gaps'])
                details = box.locator('details')
                assert details.get_attribute('open') is None
                details.locator('summary').click()
                assert details.get_attribute('open') is not None
                expect(details.locator('li').first).to_be_visible()
                page.screenshot(path=str(args.output / f'{index}-result.png'), full_page=True)
                report['responses'].append({'question': question, 'run_id': result['run_id'], 'session_id': payload['session_id'], 'status': status})
                check(f'{index}: real answer, citations, gaps, expandable trace')
                return payload

            first = ask('生成一条AI视频会预扣多少积分？', 'answered', '03-c03', hold=True)
            assert first['result']['gaps'] == [] and '20' in first['result']['answer']
            assert '24小时' not in first['result']['answer'] and '60分钟' not in first['result']['answer']
            refund = ask('那失败以后多久返还？', 'clarification_required', '04-refund')
            assert refund['session_id'] == first['session_id'] and refund['result']['clarification_reason'] == 'conflict'
            check('follow-up uses same session and preserves actual refund conflict')
            with page.expect_response(lambda r: '/api/sessions/' in r.url and r.request.method == 'DELETE') as deletion:
                page.locator('#new-chat').click()
            assert deletion.value.status == 204
            expect(page.locator('.message')).to_have_count(0)
            expect(page.locator('#welcome')).to_be_visible()
            check('new chat clears visible conversation and deletes old server session')
            ambiguous = ask('最多能加多少名活跃成员？', 'clarification_required', '05-context')
            assert ambiguous['session_id'] != first['session_id']
            assert ambiguous['result']['clarification_reason'] == 'missing_context'
            standard = ask('团队标准版。', 'answered', '06-standard')
            assert standard['session_id'] == ambiguous['session_id'] and '5' in standard['result']['answer']
            check('new session does not inherit prior topic; clarification follow-up works')
            page.route('**/api/chat', lambda route: route.fulfill(status=503, content_type='application/json', body=json.dumps({'detail':'验收注入：服务暂时不可用'}, ensure_ascii=False)))
            page.locator('#question').fill('错误提示检查')
            page.locator('#send').click()
            expect(page.locator('#error')).to_have_text('验收注入：服务暂时不可用')
            expect(page.locator('#question')).to_have_value('错误提示检查')
            expect(page.locator('#send')).to_be_enabled()
            expect(page.locator('.pending')).to_have_count(0)
            page.screenshot(path=str(args.output / '07-error.png'), full_page=True)
            page.unroute('**/api/chat')
            check('explicit HTTP 503 fixture: error shown, input restored, controls re-enabled')
            recovered = ask('团队标准版最多支持几名活跃成员？', 'answered', '08-recovered')
            expect(page.locator('#error')).to_be_hidden()
            check('real request after HTTP error recovers')
            page.set_viewport_size({'width':390, 'height':844})
            page.screenshot(path=str(args.output / '09-mobile-result.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            expect(page.locator('#send')).to_be_visible()
            page.locator('#new-chat').click()
            page.screenshot(path=str(args.output / '10-mobile-welcome.png'), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            check('390px viewport: no horizontal overflow; input, new-chat and send visible')
            assert not report['page_errors']
            check('no uncaught browser JavaScript errors')
            browser.close()
        report['status'] = 'passed'
    except Exception as exc:
        report['status'] = 'failed'
        report['failure'] = str(exc)
        raise
    finally:
        report['finished_at'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    main()
