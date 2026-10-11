"""Real FFmpeg tests: generates tiny clips, runs every video tool, verifies outputs with ffprobe."""
import hashlib
import shutil
import subprocess
import unittest

from helpers import make_env
from jarvis.tools import ToolError, video

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_frame(path, at="1"):
    return subprocess.run(["ffmpeg", "-v", "error", "-ss", at, "-i", str(path), "-frames:v", "1",
                           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout


def frame_hash(path, at="1"):
    return hashlib.sha256(raw_frame(path, at)).hexdigest()


def frame_diff(a, b, at="1"):
    """Mean absolute pixel difference between two videos at the same timestamp (0-255)."""
    fa, fb = raw_frame(a, at), raw_frame(b, at)
    assert fa and len(fa) == len(fb), "frames missing or different size"
    return sum(abs(x - y) for x, y in zip(fa, fb)) / len(fa)


@unittest.skipUnless(HAVE_FFMPEG, "ffmpeg not installed")
class VideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp, cls.cfg, cls.db, cls.ctx = make_env()

        def ff(*a):
            subprocess.run(["ffmpeg", "-y", "-v", "error", *a], check=True)

        ff("-f", "lavfi", "-i", "testsrc=duration=4:size=640x360:rate=30", "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
           "-shortest", "-pix_fmt", "yuv420p", str(cls.cfg.inbox / "a.mp4"))
        ff("-f", "lavfi", "-i", "testsrc2=duration=3:size=480x480:rate=25", "-pix_fmt", "yuv420p",
           str(cls.cfg.inbox / "silent.mp4"))
        ff("-f", "lavfi", "-i", "sine=frequency=220:duration=2", str(cls.cfg.inbox / "music.wav"))
        cls.originals = {p.name: sha(p) for p in cls.cfg.inbox.iterdir()}

    def info(self, rel):
        return video.probe(self.ctx, self.cfg.workspace / rel)

    def test_01_trim(self):
        video.video_trim(self.ctx, "inbox/a.mp4", "0.5", "2.5", "t", "cut")
        self.assertAlmostEqual(self.info("output/t/cut.mp4")["duration"], 2.0, delta=0.2)

    def test_02_resize_shorts_and_landscape_and_square(self):
        for preset, size in (("shorts", (1080, 1920)), ("landscape", (1920, 1080)), ("square", (1080, 1080))):
            video.video_resize(self.ctx, "inbox/a.mp4", preset, "fill", "t", f"r-{preset}")
            i = self.info(f"output/t/r-{preset}.mp4")
            self.assertEqual((i["width"], i["height"]), size, preset)
        video.video_resize(self.ctx, "inbox/a.mp4", "shorts", "fit", "t", "r-fit")
        self.assertEqual(self.info("output/t/r-fit.mp4")["height"], 1920)

    def test_03_join_with_and_without_audio_and_fade(self):
        video.video_join(self.ctx, ["inbox/a.mp4", "inbox/silent.mp4"], "landscape", "none", 0.5, "t", "join")
        j = self.info("output/t/join.mp4")
        self.assertAlmostEqual(j["duration"], 7.0, delta=0.3)
        self.assertTrue(j["has_audio"])
        self.assertEqual((j["width"], j["height"]), (1920, 1080))
        video.video_join(self.ctx, ["inbox/a.mp4", "inbox/silent.mp4", "inbox/a.mp4"], "shorts", "fade", 0.5, "t", "joinfade")
        jf = self.info("output/t/joinfade.mp4")
        self.assertAlmostEqual(jf["duration"], 4 + 3 + 4 - 1.0, delta=0.3)
        self.assertEqual(jf["height"], 1920)

    def test_04_join_validation(self):
        with self.assertRaises(ToolError):
            video.video_join(self.ctx, ["inbox/a.mp4"])
        with self.assertRaises(ToolError):
            video.video_join(self.ctx, ["inbox/a.mp4", "inbox/silent.mp4"], transition="wipe")
        with self.assertRaises(ToolError):
            video.video_join(self.ctx, ["inbox/a.mp4", "inbox/silent.mp4"], transition="fade", transition_seconds=5)

    def test_05_subtitles_really_change_the_picture(self):
        msg = video.srt_from_script(self.ctx, "Namaste dosto aaj hum ek mast video banayenge jo bahut kaam ka hai", 4, 5, "t", "subs")
        self.assertIn("approximate", msg.lower())
        srt = (self.cfg.output / "t" / "subs.srt").read_text()
        self.assertIn("00:00:00,000 -->", srt)
        video.video_add_subtitles(self.ctx, "inbox/a.mp4", "output/t/subs.srt", 28, "bottom", "t", "subbed")
        self.assertNotEqual(frame_hash(self.cfg.output / "t" / "subbed.mp4"), frame_hash(self.cfg.inbox / "a.mp4"))

    def test_06_write_srt_validates_timing(self):
        video.write_srt(self.ctx, [{"start": 0, "end": 1.5, "text": "Hi"}, {"start": 1.5, "end": 3, "text": "Bye"}], "t", "exact")
        self.assertIn("00:00:01,500 --> 00:00:03,000", (self.cfg.output / "t" / "exact.srt").read_text())
        with self.assertRaises(ToolError):
            video.write_srt(self.ctx, [{"start": 2, "end": 1, "text": "x"}])
        with self.assertRaises(ToolError):
            video.write_srt(self.ctx, [{"start": 0, "end": 2, "text": "a"}, {"start": 1, "end": 3, "text": "b"}])
        with self.assertRaises(ToolError):
            video.write_srt(self.ctx, [{"text": "no timing"}])

    def test_07_text_overlay_appears_only_in_window(self):
        video.video_text_overlay(self.ctx, "inbox/a.mp4", "Hello: it's 100%, JARVIS", 1.0, 3.0, "center", 40, "yellow", "t", "ov")
        out = self.cfg.output / "t" / "ov.mp4"
        src = self.cfg.inbox / "a.mp4"
        inside = frame_diff(out, src, "2")
        outside = frame_diff(out, src, "3.5")
        self.assertGreater(inside, 3 * outside + 0.5, f"overlay not visible inside window ({inside} vs {outside})")
        self.assertLess(outside, 3.0, "overlay leaked outside its time window")

    def test_08_normalize_audio_and_no_audio_error(self):
        video.video_normalize_audio(self.ctx, "inbox/a.mp4", "t", "norm")
        self.assertTrue(self.info("output/t/norm.mp4")["has_audio"])
        with self.assertRaises(ToolError):
            video.video_normalize_audio(self.ctx, "inbox/silent.mp4")

    def test_09_music_needs_license_confirmation(self):
        with self.assertRaises(ToolError):
            video.video_add_music(self.ctx, "inbox/a.mp4", "inbox/music.wav")
        video.video_add_music(self.ctx, "inbox/a.mp4", "inbox/music.wav", True, 0.2, "t", "mus")
        m = self.info("output/t/mus.mp4")
        self.assertTrue(m["has_audio"])
        self.assertAlmostEqual(m["duration"], 4.0, delta=0.3)
        video.video_add_music(self.ctx, "inbox/silent.mp4", "inbox/music.wav", True, 0.2, "t", "mus2")
        self.assertTrue(self.info("output/t/mus2.mp4")["has_audio"])

    def test_10_extract_frame_and_info_and_bad_inputs(self):
        self.assertIn("Frame saved", video.video_extract_frame(self.ctx, "inbox/a.mp4", "1", "t", "thumb"))
        self.assertTrue((self.cfg.output / "t" / "thumb.jpg").stat().st_size > 1000)
        self.assertIn("640x360", video.video_info(self.ctx, "inbox/a.mp4"))
        with self.assertRaises(ToolError):
            video.video_trim(self.ctx, "inbox/a.mp4", "abc; rm -rf /", "2")
        with self.assertRaises(ToolError):
            video.video_trim(self.ctx, "inbox/missing.mp4", "0", "1")
        with self.assertRaises(ToolError):
            video.video_trim(self.ctx, "../../etc/passwd", "0", "1")
        (self.cfg.projects / "fake.mp4").write_text("not a video")
        with self.assertRaises(ToolError):
            video.video_info(self.ctx, "projects/fake.mp4")

    def test_11_never_overwrites_and_originals_untouched(self):
        a = video.video_trim(self.ctx, "inbox/a.mp4", "0", "1", "t", "same")
        b = video.video_trim(self.ctx, "inbox/a.mp4", "0", "1", "t", "same")
        self.assertNotEqual(a.split("->")[1].split()[0], b.split("->")[1].split()[0])
        now = {p.name: sha(p) for p in self.cfg.inbox.iterdir()}
        self.assertEqual(now, self.originals)


if __name__ == "__main__":
    unittest.main()
