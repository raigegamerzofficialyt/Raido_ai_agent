import json
import subprocess
import threading
import unittest

from helpers import FakeClient, make_env, text_resp, tool_resp
from jarvis.server import make_server
from jarvis.talk import Talker, chunks, clean_for_speech, decide


class Phone:
    """Fake termux commands: records calls, returns scripted speech-to-text results."""

    def __init__(self, heard):
        self.heard, self.calls = list(heard), []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        out = self.heard.pop(0) if cmd[0] == "termux-speech-to-text" and self.heard else ""
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    def spoken(self):
        return " ".join(c[-1] for c in self.calls if c[0] == "termux-tts-speak")


class TalkTests(unittest.TestCase):
    def serve(self, script):
        self.tmp, self.cfg, self.db, _ = make_env()
        self.client = FakeClient(script)
        self.httpd = make_server(self.cfg, self.client, port=0)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (self.httpd.shutdown(), self.httpd.server_close()))

    def talker(self, heard):
        self.phone = Phone(heard)
        return Talker(self.base, self.cfg.token, runner=self.phone, poll=0.05)

    def test_helpers(self):
        self.assertEqual(clean_for_speech("**Done** [doc](http://x.com) see https://a.b ok"), "Done doc see link ok")
        self.assertTrue(all(len(c) <= 40 for c in chunks("Ek. Do teen. Chaar paanch chhe saat. Aath.", 40)))

    def test_hear_ask_speak(self):
        self.serve([text_resp("Theek hai, **ho gaya**.")])
        t = self.talker(["ek file bana do"])
        self.assertEqual(t.turn(), "ok")
        self.assertEqual(self.phone.spoken(), "Theek hai, ho gaya .")
        self.assertIn("VOICE MODE IS ON", self.client.calls[0]["system"])
        self.assertEqual(self.client.calls[0]["messages"][0]["content"][0]["text"], "ek file bana do")

    def test_stop_word_and_silence(self):
        self.serve([])
        t = self.talker(["Jarvis band karo", ""])
        self.assertEqual(t.turn(), "stop")
        self.assertEqual(t.turn(), "empty")
        self.assertEqual(self.client.calls, [])

    def test_missing_termux_api_does_not_crash(self):
        def boom(*a, **k):
            raise FileNotFoundError
        t = Talker("http://127.0.0.1:1", "x", runner=boom)
        self.assertEqual(t.listen(), "")
        t.speak("hello")
        t.notify("i", "t", "c")

    def test_approval_becomes_notification_with_tap_buttons_no_token(self):
        self.serve([tool_resp("delete_file", {"path": "projects/x.md"}), text_resp("Permission chahiye.")])
        (self.cfg.projects / "x.md").write_text("hi")
        t = self.talker(["x.md delete kar do"])
        self.assertEqual(t.turn("/proj", "python"), "ok")
        note = [c for c in self.phone.calls if c[0] == "termux-notification"]
        self.assertEqual(len(note), 1)
        cmd = note[0]
        self.assertIn("--button1-action", cmd)
        acts = [cmd[i + 1] for i, x in enumerate(cmd) if x.endswith("-action")]
        self.assertTrue(acts[0].endswith("decide 1 yes") and acts[1].endswith("decide 1 no"))
        self.assertNotIn(self.cfg.token, " ".join(cmd))
        self.assertTrue((self.cfg.projects / "x.md").exists())  # nothing deleted without the tap
        self.assertIn("permission", self.phone.spoken().lower())
        # tapping "Haan" = decide()
        self.assertEqual(decide(t, 1, False), "denied")
        self.assertTrue((self.cfg.projects / "x.md").exists())


if __name__ == "__main__":
    unittest.main()
