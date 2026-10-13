package com.raido.jarvis

import org.json.JSONArray
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

data class Action(val name: String, val args: JSONObject)
data class Reply(val text: String, val actions: List<Action>, val error: String?)

/** Talks to Google's Gemini API directly from the phone. Keeps the conversation for one assistant session. */
class Brain(private val store: Store) {
    private val history = JSONArray()

    private fun systemPrompt(): String {
        val langRule = when (store.lang) {
            "hindi" -> "Reply in Hindi, Devanagari script only."
            "english" -> "Reply in simple, clear English."
            else -> "Reply in Hinglish (Hindi written in Roman letters), the way the user speaks."
        }
        return """You are JARVIS, the user's personal voice assistant on their Android phone. You talk like a friendly, capable friend.
Your reply is read aloud: at most 3 short spoken sentences, no markdown, no emoji, no URLs, no lists. $langRule
You can ONLY act through the provided functions (open_app, set_timer, set_alarm, web_search, dial, send_sms). Every function call is shown to the user, who must tap Haan before it runs; say briefly what you want to do.
Never say something is done unless a function result confirms it. If you cannot do something, say so plainly instead of pretending.
Never ask for passwords, OTPs, card or bank details. If the user asks about private data you cannot access, say you cannot.
For send_sms you only prepare the message; the user presses send themselves."""
    }

    private fun tools(): JSONArray {
        fun fn(name: String, desc: String, props: JSONObject, req: List<String>) = JSONObject()
            .put("name", name).put("description", desc)
            .put("parameters", JSONObject().put("type", "object").put("properties", props).put("required", JSONArray(req)))
        fun s(d: String) = JSONObject().put("type", "string").put("description", d)
        fun i(d: String) = JSONObject().put("type", "integer").put("description", d)
        val decls = JSONArray()
            .put(fn("open_app", "Open an installed app by its name.", JSONObject().put("name", s("App name, e.g. WhatsApp")), listOf("name")))
            .put(fn("set_timer", "Start a countdown timer.", JSONObject().put("seconds", i("Length in seconds")).put("label", s("Optional label")), listOf("seconds")))
            .put(fn("set_alarm", "Set an alarm at a clock time (24-hour).", JSONObject().put("hour", i("0-23")).put("minute", i("0-59")).put("label", s("Optional label")), listOf("hour", "minute")))
            .put(fn("web_search", "Open a web search in the browser.", JSONObject().put("query", s("Search text")), listOf("query")))
            .put(fn("dial", "Open the phone dialer with a number. The user presses call.", JSONObject().put("number", s("Phone number digits")), listOf("number")))
            .put(fn("send_sms", "Open the messages app with a prepared text. The user presses send.", JSONObject().put("number", s("Phone number")).put("text", s("Message text")), listOf("number", "text")))
        return JSONArray().put(JSONObject().put("functionDeclarations", decls))
    }

    fun ask(userText: String): Reply {
        history.put(JSONObject().put("role", "user").put("parts", JSONArray().put(JSONObject().put("text", userText))))
        return call()
    }

    /** After the user decided on proposed actions: report each outcome back to the model. */
    fun continueWith(outcomes: List<Pair<String, String>>): Reply {
        val parts = JSONArray()
        for ((name, out) in outcomes) {
            val resp = JSONObject().put(if (out.startsWith("ERROR") || out.startsWith("DENIED")) "error" else "result", out)
            parts.put(JSONObject().put("functionResponse", JSONObject().put("name", name).put("response", resp)))
        }
        history.put(JSONObject().put("role", "user").put("parts", parts))
        return call()
    }

    private fun call(): Reply {
        if (store.apiKey.isEmpty()) return Reply("", emptyList(), "Gemini key set nahi hai. JARVIS app me key daalo.")
        val body = JSONObject()
            .put("systemInstruction", JSONObject().put("parts", JSONArray().put(JSONObject().put("text", systemPrompt()))))
            .put("contents", history)
            .put("tools", tools())
            .put("generationConfig", JSONObject().put("maxOutputTokens", 1024))
            .toString()
        var last = "Network error"
        for (attempt in 0..2) {
            try {
                val c = URL("https://generativelanguage.googleapis.com/v1beta/models/${store.model}:generateContent")
                    .openConnection() as HttpURLConnection
                c.requestMethod = "POST"
                c.connectTimeout = 15000
                c.readTimeout = 60000
                c.doOutput = true
                c.setRequestProperty("Content-Type", "application/json")
                c.setRequestProperty("x-goog-api-key", store.apiKey)
                c.outputStream.use { it.write(body.toByteArray()) }
                val code = c.responseCode
                if (code in 200..299) {
                    return parse(c.inputStream.bufferedReader().readText())
                }
                val err = (c.errorStream?.bufferedReader()?.readText() ?: "").take(200)
                last = "Gemini error $code"
                if (code == 400 || code == 401 || code == 403 || code == 404) {
                    return Reply("", emptyList(), "$last. Key ya model check karo.")
                }
                if (err.isNotEmpty() && attempt == 2) last += ": $err"
            } catch (e: Exception) {
                last = "Internet ya network dikkat: ${e.javaClass.simpleName}"
            }
            Thread.sleep(1500)
        }
        return Reply("", emptyList(), last)
    }

    private fun parse(raw: String): Reply {
        val cands = JSONObject(raw).optJSONArray("candidates")
        if (cands == null || cands.length() == 0) return Reply("", emptyList(), "Gemini ne jawab nahi diya.")
        val content = cands.getJSONObject(0).optJSONObject("content")
            ?: return Reply("", emptyList(), "Gemini ne khaali jawab diya.")
        history.put(content) // keep model turn exactly as returned (includes thought signatures)
        val parts = content.optJSONArray("parts") ?: JSONArray()
        val text = StringBuilder()
        val actions = ArrayList<Action>()
        for (i in 0 until parts.length()) {
            val p = parts.getJSONObject(i)
            if (p.has("functionCall")) {
                val fc = p.getJSONObject("functionCall")
                actions.add(Action(fc.getString("name"), fc.optJSONObject("args") ?: JSONObject()))
            } else if (p.has("text") && !p.optBoolean("thought", false)) {
                text.append(p.getString("text")).append(' ')
            }
        }
        return Reply(text.toString().trim(), actions, null)
    }
}
