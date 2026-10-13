package com.raido.jarvis

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.RadioButton
import android.widget.RadioGroup
import android.widget.ScrollView
import android.widget.TextView

/** One simple screen: key, language, mic permission, and the button that makes JARVIS the phone's assistant. */
class SettingsActivity : Activity() {
    private lateinit var store: Store
    private lateinit var info: TextView

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = Store(this)
        val col = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(20), dp(24), dp(20), dp(24)) }
        fun text(s: String, size: Float = 15f) = TextView(this).apply { text = s; textSize = size; setPadding(0, dp(8), 0, dp(4)) }
        fun btn(s: String, f: () -> Unit) = Button(this).apply { text = s; setOnClickListener { f() } }

        col.addView(text("JARVIS", 26f))
        info = text("")
        col.addView(info)

        col.addView(text("1. Gemini API key (sirf is phone me save hogi):"))
        val key = EditText(this).apply {
            hint = if (store.apiKey.isEmpty()) "Key yahan paste karo" else "Key save hai (badalne ke liye nayi paste karo)"
            inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
        }
        col.addView(key)

        col.addView(text("2. Bhasha:"))
        val group = RadioGroup(this)
        val opts = listOf("hinglish" to "Hinglish", "hindi" to "हिन्दी", "english" to "English")
        for ((v, label) in opts) {
            group.addView(RadioButton(this).apply { text = label; tag = v; isChecked = store.lang == v })
        }
        col.addView(group)

        col.addView(btn("Save karo") {
            if (key.text.isNotBlank()) store.apiKey = key.text.toString()
            val checked = group.findViewById<RadioButton>(group.checkedRadioButtonId)
            store.lang = (checked?.tag as? String) ?: "hinglish"
            key.setText("")
            refresh()
        })
        col.addView(text("3. Mic permission:"))
        col.addView(btn("Mic permission do") { requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 1) })
        col.addView(text("4. JARVIS ko phone ka assistant banao:"))
        col.addView(btn("Assistant settings kholo") {
            try { startActivity(Intent(Settings.ACTION_VOICE_INPUT_SETTINGS)) }
            catch (e: Exception) { startActivity(Intent(Settings.ACTION_SETTINGS)) }
        })
        col.addView(text(
            "Wahan 'Digital assistant app' me JARVIS chuno. Samsung par: Settings > Apps > Choose default apps > Digital assistant app. " +
            "Phir power/side button ko long-press par 'Wake Digital assistant' par set karo (Settings > Advanced features > Side button). " +
            "Ab button dabake rakho aur JARVIS khul jayega.\n\n" +
            "Dhyan: 'Hey Google' jaisa hamesha-sunne wala shabd third-party app ke liye Android me allowed nahi hai. " +
            "Har kaam se pehle JARVIS tumse Haan/Nahi puchta hai."
        ))
        setContentView(ScrollView(this).apply { addView(col, ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT) })
        refresh()
    }

    override fun onResume() { super.onResume(); refresh() }

    private fun refresh() {
        val mic = checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        info.text = "Key: " + (if (store.apiKey.isEmpty()) "NAHI daali" else "save hai") +
            "  |  Mic: " + (if (mic) "OK" else "permission chahiye") + "  |  Bhasha: " + store.lang
    }
}
