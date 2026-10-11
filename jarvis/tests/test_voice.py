import json
import threading
import time
import unittest
import urllib.request

from helpers import FakeClient, make_agent, make_env, text_resp
from jarvis.server import make_server


class VoicePromptTests(unittest.TestCase):
    def test_voice_note_only_when_voice_set(self):
        agent, *_ = make_agent([])
        self.assertNotIn("VOICE MODE IS ON", agent.system_prompt())
        self.assertNotIn("VOICE MODE IS ON", agent.system_prompt(None))
        p = agent.system_prompt("hinglish")
        self.assertIn("VOICE MODE IS ON", p)
        self.assertIn("Roman letters", p)
        self.assertIn("Devanagari", agent.system_prompt("hindi"))
        self.assertIn("English", agent.system_prompt("english"))

    def test_run_passes_voice_note_to_model(self):
        agent, client, *_ = make_agent([text_resp("Theek hai."), text_resp("ok")])
        agent.run("namaste", voice="hinglish")
        agent.run("hi")
        self.assertIn("VOICE MODE IS ON", client.calls[0]["system"])
        self.assertNotIn("VOICE MODE IS ON", client.calls[1]["system"])


class VoiceServerTests(unittest.TestCase):
    def post(self, body):
        r = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/chat", data=json.dumps(body).encode(), method="POST",
                                   headers={"Content-Type": "application/json", "X-Jarvis-Token": self.cfg.token})
        with urllib.request.urlopen(r) as resp:
            return json.loads(resp.read())["task_id"]

    def wait(self, task_id):
        for _ in range(50):
            t = self.db.get_task(task_id) if hasattr(self.db, "get_task") else None
            if t and t["status"] != "running":
                return
            time.sleep(0.1)

    def serve(self, n):
        self.tmp, self.cfg, self.db, _ = make_env()
        self.client = FakeClient([text_resp("ok")] * n)
        self.httpd = make_server(self.cfg, self.client, port=0)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (self.httpd.shutdown(), self.httpd.server_close()))

    def test_chat_voice_flag_and_language(self):
        self.serve(3)
        self.wait(self.post({"text": "a", "voice": True, "voice_lang": "english"}))
        self.wait(self.post({"text": "b", "voice": True, "voice_lang": "klingon"}))
        self.wait(self.post({"text": "c"}))
        time.sleep(0.3)
        systems = [c["system"] for c in self.client.calls]
        self.assertEqual(len(systems), 3)
        self.assertIn("VOICE MODE IS ON", systems[0])
        self.assertIn("simple, clear English", systems[0])
        self.assertIn("Roman letters", systems[1])  # unknown language falls back to hinglish
        self.assertNotIn("VOICE MODE IS ON", systems[2])


class UiVoiceControlsTests(unittest.TestCase):
    def test_ui_has_voice_controls_and_no_secrets(self):
        import pathlib
        html = (pathlib.Path(__file__).resolve().parent.parent / "jarvis" / "ui.html").read_text()
        for needle in ("webkitSpeechRecognition", "speechSynthesis", "voice_lang", 'id="mic"', 'id="vmode"', "wakeLock"):
            self.assertIn(needle, html)


if __name__ == "__main__":
    unittest.main()
