package com.raido.jarvis

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.service.voice.VoiceInteractionSession
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.view.Gravity
import android.view.View
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import java.util.Locale

/**
 * The panel that appears when the user invokes the assistant (power-button long-press, home-button/gesture hold).
 * Flow: listen -> Gemini -> (user taps Haan for any phone action) -> speak -> listen again.
 */
class JarvisSession(private val ctx: Context) : VoiceInteractionSession(ctx) {
    private val main = Handler(Looper.getMainLooper())
    private val store = Store(ctx)
    private var brain = Brain(store)
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var recognizer: SpeechRecognizer? = null
    private var statusView: TextView? = null
    private var replyView: TextView? = null
    private var confirmBox: LinearLayout? = null
    private var confirmText: TextView? = null
    private var pending: List<Action> = emptyList()
    private var silentTurns = 0

    private fun dp(v: Int) = (v * ctx.resources.displayMetrics.density).toInt()

    override fun onCreateContentView(): View {
        val root = FrameLayout(ctx)
        root.setOnClickListener { hide() }
        val card = LinearLayout(ctx)
        card.orientation = LinearLayout.VERTICAL
        card.setPadding(dp(20), dp(18), dp(20), dp(24))
        card.background = GradientDrawable().apply {
            setColor(Color.parseColor("#F2101820"))
            cornerRadii = floatArrayOf(dp(24).toFloat(), dp(24).toFloat(), dp(24).toFloat(), dp(24).toFloat(), 0f, 0f, 0f, 0f)
        }
        card.isClickable = true

        statusView = TextView(ctx).apply { setTextColor(Color.parseColor("#7FD6FF")); textSize = 15f; text = "JARVIS" }
        replyView = TextView(ctx).apply { setTextColor(Color.WHITE); textSize = 18f; setPadding(0, dp(8), 0, dp(8)) }
        confirmText = TextView(ctx).apply { setTextColor(Color.parseColor("#FFD479")); textSize = 16f }
        val yes = Button(ctx).apply { text = "Haan"; setOnClickListener { decide(true) } }
        val no = Button(ctx).apply { text = "Nahi"; setOnClickListener { decide(false) } }
        val row = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL; addView(yes); addView(no) }
        confirmBox = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
            addView(confirmText); addView(row)
        }
        val mic = Button(ctx).apply { text = "Bolo"; setOnClickListener { startListening() } }
        val close = Button(ctx).apply { text = "Band"; setOnClickListener { hide() } }
        val bottom = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL; addView(mic); addView(close) }

        card.addView(statusView); card.addView(replyView); card.addView(confirmBox); card.addView(bottom)
        root.addView(card, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM))
        return root
    }

    override fun onShow(args: Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        brain = Brain(store) // fresh conversation each time the assistant is opened
        pending = emptyList()
        silentTurns = 0
        replyView?.text = ""
        confirmBox?.visibility = View.GONE
        initTts()
        startListening()
    }

    override fun onHide() {
        stopAll()
        super.onHide()
    }

    override fun onDestroy() {
        stopAll()
        tts?.shutdown()
        tts = null
        super.onDestroy()
    }

    private fun stopAll() {
        try { recognizer?.cancel(); recognizer?.destroy() } catch (e: Exception) { }
        recognizer = null
        try { tts?.stop() } catch (e: Exception) { }
    }

    private fun status(s: String) { statusView?.text = s }

    private fun initTts() {
        if (tts != null) { applyTtsLang(); return }
        tts = TextToSpeech(ctx) { st ->
            ttsReady = st == TextToSpeech.SUCCESS
            if (ttsReady) applyTtsLang()
        }
    }

    private fun applyTtsLang() {
        val loc = if (store.lang == "hindi") Locale("hi", "IN") else Locale("en", "IN")
        tts?.language = loc
    }

    private fun speak(text: String, then: (() -> Unit)?) {
        val clean = text.replace(Regex("https?://\\S+"), " link ").replace(Regex("[*_#`>|~\\[\\]]"), " ").replace(Regex("\\s+"), " ").trim()
        val t = tts
        if (!ttsReady || t == null || clean.isEmpty()) { then?.invoke(); return }
        status("Bol raha hoon...")
        val id = "u" + System.nanoTime()
        t.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(utteranceId: String?) {}
            override fun onDone(utteranceId: String?) { if (utteranceId == id) main.post { then?.invoke() } }
            @Deprecated("Deprecated in Java")
            override fun onError(utteranceId: String?) { if (utteranceId == id) main.post { then?.invoke() } }
        })
        t.speak(clean, TextToSpeech.QUEUE_FLUSH, null, id)
    }

    private fun startListening() {
        if (store.apiKey.isEmpty()) { replyView?.text = "Pehle JARVIS app kholkar Gemini key daalo."; status("Key chahiye"); return }
        if (ctx.checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            replyView?.text = "Mic permission chahiye. JARVIS app kholkar 'Mic permission do' dabao."; status("Permission chahiye"); return
        }
        if (!SpeechRecognizer.isRecognitionAvailable(ctx)) { replyView?.text = "Is phone me speech recognition nahi mila."; return }
        stopAll()
        tts?.stop()
        val google = ComponentName("com.google.android.googlequicksearchbox", "com.google.android.voicesearch.serviceapi.GoogleRecognitionService")
        val r = try { SpeechRecognizer.createSpeechRecognizer(ctx, google) } catch (e: Exception) { SpeechRecognizer.createSpeechRecognizer(ctx) }
        recognizer = r
        r.setRecognitionListener(object : RecognitionListener {
            override fun onReadyForSpeech(params: Bundle?) { status("Sun raha hoon... boliye") }
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() { status("Samajh raha hoon...") }
            override fun onEvent(eventType: Int, params: Bundle?) {}
            override fun onPartialResults(partialResults: Bundle?) {
                val p = partialResults?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
                if (!p.isNullOrEmpty()) replyView?.text = p
            }
            override fun onError(error: Int) {
                if (error == SpeechRecognizer.ERROR_CLIENT) return // we cancelled it ourselves
                if (error == SpeechRecognizer.ERROR_NO_MATCH || error == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) {
                    silentTurns++
                    if (silentTurns >= 2) { hide() } else { status("Kuch sunai nahi diya"); }
                } else {
                    status("Mic error ($error)")
                    replyView?.text = "Voice sunne me dikkat (code $error). Internet aur mic permission check karo."
                }
            }
            override fun onResults(results: Bundle?) {
                val text = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()?.trim().orEmpty()
                if (text.isEmpty()) { status("Kuch sunai nahi diya"); return }
                silentTurns = 0
                replyView?.text = text
                handle(text)
            }
        })
        val i = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            .putExtra(RecognizerIntent.EXTRA_LANGUAGE, if (store.lang == "english") "en-IN" else "hi-IN")
            .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
        r.startListening(i)
    }

    private fun handle(text: String) {
        val l = text.lowercase()
        if (listOf("band karo", "bye jarvis", "bas karo", "बंद करो", "बस करो").any { l.contains(it) }) { hide(); return }
        status("Soch raha hoon...")
        Thread { val res = brain.ask(text); main.post { render(res) } }.start()
    }

    private fun render(res: Reply) {
        if (res.error != null) {
            status("Error"); replyView?.text = res.error
            speak(res.error, null)
            return
        }
        replyView?.text = res.text
        if (res.actions.isNotEmpty()) {
            pending = res.actions
            confirmText?.text = res.actions.joinToString("\n") { Actions.describe(it) }
            confirmBox?.visibility = View.VISIBLE
            status("Tumhari permission chahiye")
            speak((if (res.text.isNotEmpty()) res.text + " " else "") + "Haan ya Nahi dabao.", null)
        } else {
            confirmBox?.visibility = View.GONE
            speak(res.text.ifEmpty { "Theek hai." }) { startListening() }
        }
    }

    private fun decide(yes: Boolean) {
        val acts = pending
        pending = emptyList()
        confirmBox?.visibility = View.GONE
        if (acts.isEmpty()) return
        status("Kar raha hoon...")
        val outcomes = acts.map { a ->
            a.name to (if (yes) Actions.execute(ctx, a) else "DENIED: user ne mana kar diya, kuch nahi kiya gaya.")
        }
        Thread { val res = brain.continueWith(outcomes); main.post { render(res) } }.start()
    }
}
