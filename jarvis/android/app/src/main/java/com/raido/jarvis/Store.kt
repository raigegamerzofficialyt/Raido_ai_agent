package com.raido.jarvis

import android.content.Context

/** Private on-device settings. The API key stays in this app's private storage; it is never logged or uploaded anywhere except to Google's Gemini API. */
class Store(ctx: Context) {
    private val p = ctx.getSharedPreferences("jarvis", Context.MODE_PRIVATE)

    var apiKey: String
        get() = p.getString("key", "") ?: ""
        set(v) { p.edit().putString("key", v.trim()).apply() }

    var model: String
        get() = p.getString("model", "gemini-flash-latest") ?: "gemini-flash-latest"
        set(v) { p.edit().putString("model", v.trim().ifEmpty { "gemini-flash-latest" }).apply() }

    /** hinglish | hindi | english */
    var lang: String
        get() = p.getString("lang", "hinglish") ?: "hinglish"
        set(v) { p.edit().putString("lang", v).apply() }
}
