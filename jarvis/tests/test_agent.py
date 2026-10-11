import unittest

from helpers import ROOT, make_agent, text_resp, tool_resp  # noqa: F401
from jarvis.claude_client import ClaudeError


class AgentTests(unittest.TestCase):
    def test_tool_call_then_final_answer(self):
        agent, client, cfg, db, ctx = make_agent([
            tool_resp("write_file", {"path": "projects/n.md", "content": "hi"}, "t1", "Likh raha hoon"),
            text_resp("Ho gaya: file bana di."),
        ])
        out = agent.run("ek note bana")
        self.assertEqual(out["status"], "done")
        self.assertEqual(out["reply"], "Ho gaya: file bana di.")
        self.assertEqual((cfg.projects / "n.md").read_text(), "hi")
        # second call must have received the real tool_result
        last = client.calls[1]["messages"][-1]
        self.assertEqual(last["content"][0]["type"], "tool_result")
        self.assertIn("Written projects/n.md", last["content"][0]["content"])
        kinds = [e["kind"] for e in db.get_task(out["task_id"])["events"]]
        self.assertIn("tool", kinds)

    def test_system_prompt_contains_rules_skills_and_memory(self):
        agent, client, cfg, db, ctx = make_agent([text_resp("ok")])
        db.remember("rate", "500")
        agent.run("hi")
        system = client.calls[0]["system"]
        self.assertIn("Never say an action is done unless a tool result", system)
        self.assertIn("youtube-research", system)
        self.assertIn("rate: 500", system)
        self.assertIn("Hinglish", system)

    def test_risky_tool_is_not_executed_until_approved(self):
        agent, client, cfg, db, ctx = make_agent([
            tool_resp("delete_file", {"path": "projects/keep.md"}, "t1"),
            text_resp("Approval chahiye, Approvals tab me confirm karo."),
        ])
        target = cfg.projects / "keep.md"
        target.write_text("important")
        out = agent.run("keep.md delete kar")
        self.assertEqual(out["status"], "waiting_approval")
        self.assertTrue(target.exists(), "file must NOT be deleted before approval")
        result = client.calls[1]["messages"][-1]["content"][0]["content"]
        self.assertTrue(result.startswith("PENDING_USER_APPROVAL"))
        pending = db.list_approvals("pending")
        self.assertEqual(len(pending), 1)

        res = agent.decide(pending[0]["id"], True)
        self.assertEqual(res["status"], "executed")
        self.assertFalse(target.exists())
        self.assertTrue((cfg.trash / "keep.md").exists())
        with self.assertRaises(Exception):
            agent.decide(pending[0]["id"], True)  # cannot approve twice

    def test_deny_keeps_file_and_tells_claude(self):
        agent, client, cfg, db, ctx = make_agent([tool_resp("delete_file", {"path": "projects/k.md"}), text_resp("ok"),
                                                  text_resp("theek hai")])
        (cfg.projects / "k.md").write_text("x")
        agent.run("delete k")
        aid = db.list_approvals("pending")[0]["id"]
        self.assertEqual(agent.decide(aid, False)["status"], "denied")
        self.assertTrue((cfg.projects / "k.md").exists())
        agent.run("ab kya hua?")
        flat = str(client.calls[-1]["messages"])
        self.assertIn("DENIED approval", flat)

    def test_tool_errors_are_reported_and_agent_recovers(self):
        agent, client, cfg, db, ctx = make_agent([
            tool_resp("read_file", {"path": "projects/missing.md"}, "t1"),
            tool_resp("no_such_tool", {}, "t2"),
            tool_resp("read_file", {"bogus_arg": 1}, "t3"),
            text_resp("File nahi mili, aur tools me galti thi."),
        ])
        out = agent.run("missing file padh")
        self.assertEqual(out["status"], "done")
        errs = [m["content"][0] for c in client.calls[1:] for m in c["messages"][-1:]]
        self.assertTrue(all(e.get("is_error") for e in errs[:3]))
        self.assertIn("Not found", errs[0]["content"])
        self.assertIn("Unknown tool", errs[1]["content"])
        self.assertIn("Invalid arguments", errs[2]["content"])

    def test_claude_api_failure_is_a_failed_task_not_a_crash(self):
        agent, client, cfg, db, ctx = make_agent([ClaudeError("boom", 500)])
        out = agent.run("hello")
        self.assertEqual(out["status"], "failed")
        self.assertIn("boom", out["reply"])
        self.assertEqual(db.get_task(out["task_id"])["status"], "failed")

    def test_daily_token_budget_stops_the_loop_before_calling_claude(self):
        agent, client, cfg, db, ctx = make_agent([text_resp("should not be reached")], daily_token_limit=100)
        db.add_usage(80, 40)
        out = agent.run("kuch bhi")
        self.assertIn("token limit", out["reply"])
        self.assertEqual(client.calls, [])

    def test_usage_is_recorded(self):
        agent, client, cfg, db, ctx = make_agent([text_resp("ok", tokens=(100, 20))])
        agent.run("hi")
        self.assertEqual(db.usage_today(), 120)

    def test_step_limit_prevents_infinite_tool_loops(self):
        script = [tool_resp("list_files", {}, f"t{i}") for i in range(10)]
        agent, client, cfg, db, ctx = make_agent(script, max_steps=3)
        out = agent.run("loop")
        self.assertEqual(len(client.calls), 3)
        self.assertIn("Step limit", out["reply"])

    def test_conversation_history_carries_over_and_repairs_cut_off_tool_use(self):
        agent, client, cfg, db, ctx = make_agent([text_resp("pehla jawab"), text_resp("doosra")])
        agent.run("pehla")
        agent.run("doosra sawal")
        msgs = client.calls[1]["messages"]
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
        # simulate a crash that left a dangling tool_use
        turn = db.next_turn()
        db.add_message(turn, "user", [{"type": "text", "text": "x"}])
        db.add_message(turn, "assistant", [{"type": "tool_use", "id": "dangling", "name": "list_files", "input": {}}])
        hist = agent._repair(db.recent_messages(6))
        self.assertEqual(hist[-1]["content"][0]["tool_use_id"], "dangling")
        self.assertTrue(hist[-1]["content"][0]["is_error"])

    def test_website_opening_needs_approval_unless_site_is_approved(self):
        agent, client, cfg, db, ctx = make_agent([text_resp("x")])
        cfg.approved_sites = ["youtube.com"]
        tool = agent.registry.get("open_website")
        self.assertFalse(tool.needs_approval(ctx, {"url": "https://www.youtube.com/watch?v=1"}))
        self.assertTrue(tool.needs_approval(ctx, {"url": "https://evil.example/"}))
        self.assertTrue(tool.needs_approval(ctx, {"url": "https://notyoutube.com/"}))


if __name__ == "__main__":
    unittest.main()
