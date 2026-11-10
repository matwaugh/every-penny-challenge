"""Run with: python3 -m unittest discover -s tests -p 'test_browser.py' -v.
Uses installed Python Playwright and Chromium. All data is fictional.
"""
import functools
import http.server
import json
from pathlib import Path
import threading
import unittest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STORE = 'epc-group1-session-v1'

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/'
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 900})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.external_requests = []
        self.page.on('request', lambda req: self.external_requests.append(req.url) if not req.url.startswith(self.url) else None)
        self.assertEqual(self.page.goto(self.url).status, 200)

    def tearDown(self):
        self.assertEqual(self.errors, [])
        self.assertEqual(self.external_requests, [], 'Demo journey must not contact a payment provider')
        self.context.close()

    def signup(self, level=2):
        self.page.locator('#ownerName').fill('Alex Demo')
        self.page.locator('#ownerEmail').fill('alex@example.test')
        self.page.locator(f'[data-pick="{level}"]').click()
        self.page.locator('#startChallenge').click()
        self.assertTrue(self.page.locator('#campaignMain').is_visible())

    def reserve(self):
        self.page.locator('[data-bundle="1000"]').click()
        self.page.locator('#donor').fill('Sam Demo')
        self.page.locator('#donormessage').fill('<b>Fictional</b> message')
        self.page.locator('#donate').click()
        self.assertTrue(self.page.locator('#checkout').is_visible())

    def dashboard_counts(self):
        return [int(v) for v in self.page.locator('#dashboardCounts b').all_text_contents()]

    def seed(self, transform):
        self.page.evaluate(f"""() => {{const d=JSON.parse(sessionStorage.getItem('{STORE}')); const c=d.challenges['alex@example.test:'+d.owner.level]; {transform}; sessionStorage.setItem('{STORE}',JSON.stringify(d));}}""")
        self.page.reload()

    def test_complete_donor_and_review_journey_desktop_and_mobile(self):
        for width, level in [(1280,2),(390,5),(360,10)]:
            with self.subTest(width=width, level=level):
                self.page.set_viewport_size({'width':width,'height':844})
                self.signup(level)
                self.assertEqual(self.page.locator('#mosaic .tile').count(),level*100)
                self.assertEqual(self.page.locator('.stats .stat').count(),2)
                self.assertEqual(self.page.locator('#target').count(),0)
                self.assertTrue(self.page.locator('#donate').is_disabled())
                self.page.locator('[data-bundle="1000"]').click()
                self.assertEqual(self.page.locator('#total').inner_text(),'£10.00')
                number=int(self.page.locator('#chosen').inner_text().split()[0])
                self.assertTrue(5<=number<=10)
                self.page.locator('[data-view="grid"]').click()
                self.assertEqual(self.page.locator('#grid button').count(),level*100)
                self.assertEqual(self.page.locator('#total').inner_text(),'£10.00')
                self.page.locator('#donor').fill('Sam Demo')
                self.page.locator('#donormessage').fill('<b>Fictional</b> message')
                self.page.locator('#donate').click()
                ref=self.page.locator('#checkoutRef').inner_text()
                self.assertRegex(ref,r'^EPC-\d{6}$')
                self.assertEqual(self.dashboard_counts(),[0,0,number,level*100-number])
                self.page.locator('#simulateReturn').click()
                self.assertTrue(self.page.locator('#thankyou').is_visible())
                self.assertEqual(self.page.locator('#receiptAmount').inner_text(),'£10.00')
                self.assertEqual(self.page.locator('#receiptRef').inner_text(),ref)
                squares=self.page.locator('#receiptSquares').inner_text().split(' · ')
                self.assertEqual(len(squares),number)
                self.assertEqual(sum(round(float(value[1:])*100) for value in squares),1000)
                self.assertIn('awaiting approval',self.page.locator('#receiptPrivate').inner_text())
                self.page.reload()
                self.assertEqual(self.page.locator('#receiptRef').inner_text(),ref)
                self.page.locator('#viewChallenge').click()
                self.assertEqual(self.page.locator('#raised').inner_text(),'£0.00')
                self.assertEqual(self.page.locator('#completion').inner_text(),'0% complete')
                self.assertEqual(self.page.locator('#donor').input_value(),'')
                self.page.locator('#ownerUnlock').click()
                self.assertEqual(self.page.locator('#queue b').count(),1, 'Donor message is rendered as text')
                self.page.once('dialog',lambda dialog: dialog.accept())
                self.page.get_by_role('button',name='Approve claim',exact=True).click()
                self.assertEqual(self.dashboard_counts(),[number,0,0,level*100-number])
                self.assertEqual(self.page.locator('#raised').inner_text(),'£10.00')
                self.assertIn('approved.',self.page.locator('#dashboardNotice').inner_text())
                self.page.reload()
                self.assertEqual(self.page.locator('#raised').inner_text(),'£10.00')
                self.assertFalse(self.page.locator('#ownerBar').is_visible())
                self.assertFalse(self.page.evaluate('document.documentElement.scrollWidth > innerWidth'))
                self.assertEqual(self.page.evaluate('localStorage.length'),0)
                self.page.evaluate('sessionStorage.clear()')
                self.page.goto(self.url)

    def test_manual_selection_minimum_shuffle_and_invalid_input(self):
        self.signup()
        self.page.locator('[data-view="grid"]').click()
        grid=self.page.locator('#grid button')
        grid.nth(0).click()
        self.assertTrue(self.page.locator('#donate').is_disabled())
        self.assertEqual(self.page.locator('#minnote').inner_text(),'£2 minimum donation')
        self.assertIn('£1.99',self.page.locator('#warning').inner_text())
        grid.nth(198).click()
        self.assertEqual(self.page.locator('#total').inner_text(),'£2.00')
        self.assertFalse(self.page.locator('#donate').is_disabled())
        self.page.locator('#donate').click()
        self.assertFalse(self.page.locator('#checkout').is_visible())
        self.assertIn('enter your name',self.page.locator('#warning').inner_text())
        self.page.locator('[data-bundle="1000"]').click()
        original=self.page.locator('#selectionList').text_content()
        self.page.locator('#shuffle').click()
        self.assertEqual(self.page.locator('#total').inner_text(),'£10.00')
        self.assertNotEqual(original,self.page.locator('#selectionList').text_content())
        self.page.locator('#donationValue').fill('1.999')
        self.page.locator('#suggest').click()
        self.assertIn('two decimal places',self.page.locator('#warning').inner_text())
        self.assertEqual(self.page.locator('#total').inner_text(),'£10.00')
        self.page.locator('#selectionDetails').evaluate('(e)=>e.open=true')
        self.page.locator('#selectionList button').first.click()
        self.assertLess(float(self.page.locator('#total').inner_text()[1:]),10)
        self.page.locator('#clear').click()
        self.assertEqual(self.page.locator('#total').inner_text(),'£0.00')

    def test_cancellation_reload_recovery_and_release(self):
        self.signup()
        self.reserve()
        old_ref=self.page.locator('#checkoutRef').inner_text()
        self.page.reload()
        self.assertTrue(self.page.locator('#resume').is_visible())
        self.page.locator('#resume').click()
        self.assertEqual(self.page.locator('#checkoutRef').inner_text(),old_ref)
        self.page.keyboard.press('Escape')
        self.assertEqual(self.dashboard_counts(),[0,0,0,200])
        self.assertEqual(self.page.locator('#total').inner_text(),'£10.00')
        self.assertEqual(self.page.locator('#donor').input_value(),'Sam Demo')
        self.page.locator('#donate').click()
        self.assertNotEqual(self.page.locator('#checkoutRef').inner_text(),old_ref)
        self.page.locator('#simulateReturn').click()
        self.page.locator('#viewChallenge').click()
        self.page.locator('#ownerUnlock').click()
        self.page.once('dialog',lambda dialog:dialog.dismiss())
        self.page.get_by_role('button',name='Release squares',exact=True).click()
        self.assertGreater(self.dashboard_counts()[1],0)
        self.page.once('dialog',lambda dialog:dialog.accept())
        self.page.get_by_role('button',name='Release squares',exact=True).click()
        self.assertEqual(self.dashboard_counts(),[0,0,0,200])

    def test_expiry_and_one_hour_recovery(self):
        self.signup()
        self.reserve()
        self.seed('c.attempt.expiresAt=Date.now()-1')
        self.assertFalse(self.page.locator('#resume').is_visible())
        self.assertEqual(self.dashboard_counts(),[0,0,0,200])
        self.assertEqual(self.page.locator('#total').inner_text(),'£10.00')
        self.assertIn('expired',self.page.locator('#campaignNotice').inner_text())
        self.seed('c.updatedAt=Date.now()-3600001')
        self.assertEqual(self.page.locator('#total').inner_text(),'£0.00')
        self.assertEqual(self.page.locator('#donor').input_value(),'')

    def test_remainder_and_completion_boundaries(self):
        self.signup(10)
        for count,expected in [(1,'<1%'),(999,'99%'),(1000,'100%')]:
            with self.subTest(count=count):
                self.seed(f"c.claims=[{{ref:'EPC-999999',amounts:Array.from({{length:{count}}},(_,i)=>i+1),amount:200,donor:'Fictional',message:'',status:'approved'}}]")
                self.assertEqual(self.page.locator('#completion').inner_text(),expected+' complete')
                self.assertEqual(self.page.locator('#raised').inner_text(),'£2.00', 'Money does not determine completion')
        self.seed("c.claims=[{ref:'EPC-999999',amounts:Array.from({length:999},(_,i)=>i+2),amount:500499,donor:'Fictional',message:'',status:'approved'}]")
        self.assertIn('below the £2 minimum',self.page.locator('#campaignNotice').inner_text())
        self.assertTrue(self.page.locator('#donate').is_disabled())

    def test_receipt_has_no_details_in_a_new_session(self):
        self.page.goto(self.url+'?thankyou=1')
        self.assertTrue(self.page.locator('#thankyou').is_visible())
        self.assertFalse(self.page.locator('#receiptPrivate').is_visible())
        self.assertIn('original browser session',self.page.locator('#receiptNotice').inner_text())
        self.page.locator('#viewChallenge').click()
        self.assertTrue(self.page.locator('#welcome').is_visible())
        self.page.go_back()
        self.assertTrue(self.page.locator('#thankyou').is_visible())
        self.page.go_forward()
        self.assertTrue(self.page.locator('#welcome').is_visible())

    def test_reservation_expires_while_checkout_is_open(self):
        self.page.clock.install()
        self.page.reload()
        self.signup()
        self.reserve()
        self.page.clock.fast_forward(30*60*1000+1000)
        self.assertTrue(self.page.locator('#simulateReturn').is_disabled())
        self.assertIn('expired',self.page.locator('#checkoutError').inner_text())
        self.assertEqual(self.dashboard_counts(),[0,0,0,200])
        self.assertTrue(self.page.locator('#checkout').is_visible())
        self.page.locator('#cancelCheckout').click()
        self.assertFalse(self.page.locator('#checkout').is_visible())

    def test_grid_keyboard_focus_and_no_edit_during_reservation(self):
        self.signup()
        self.page.locator('[data-view="grid"]').click()
        self.page.locator('#grid button').nth(199).focus()
        self.page.keyboard.press('Enter')
        self.assertEqual(self.page.locator('#total').inner_text(),'£2.00')
        self.assertEqual(self.page.evaluate('document.activeElement.dataset.square'),'200')
        self.page.locator('#donor').fill('Sam Demo')
        self.page.locator('#donate').click()
        self.page.reload()
        self.page.locator('[data-view="grid"]').click()
        self.assertEqual(self.page.locator('#grid button:not(:disabled)').count(),0)
        self.page.locator('#resume').click()
        self.page.locator('#cancelCheckout').click()
        self.assertEqual(self.page.locator('#grid button:not(:disabled)').count(),200)

    def test_clipboard_feedback_and_receipt_square_values(self):
        self.context.grant_permissions(['clipboard-read','clipboard-write'])
        self.signup()
        self.reserve()
        expected=self.page.locator('#checkoutSquares').text_content()
        self.page.locator('#simulateReturn').click()
        self.assertEqual(self.page.locator('#receiptSquares').text_content(),expected)
        ref=self.page.locator('#receiptRef').inner_text()
        self.page.locator('#copyReference').click()
        self.page.wait_for_function("document.getElementById('receiptNotice').textContent==='Reference copied.'")
        self.assertEqual(self.page.evaluate('navigator.clipboard.readText()'),ref)
        self.page.locator('#viewChallenge').click()
        self.page.locator('#ownerUnlock').click()
        self.page.once('dialog',lambda dialog:dialog.accept())
        self.page.get_by_role('button',name='Approve claim',exact=True).click()
        self.page.go_back()
        self.assertIn('Approved.',self.page.locator('#receiptStatus').inner_text())
        self.assertEqual(self.page.locator('#receiptSquares').text_content(),expected)

    def test_session_storage_failure_prevents_checkout(self):
        self.page.add_init_script("Storage.prototype.setItem=()=>{throw new Error('Storage unavailable')}")
        self.page.reload()
        self.signup()
        self.page.locator('[data-bundle="200"]').click()
        self.assertTrue(self.page.locator('#donate').is_disabled())
        self.assertIn('storage',self.page.locator('#campaignNotice').inner_text().lower())

if __name__=='__main__': unittest.main()
