package com.raido.jarvis

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.AlarmClock

/** Phone actions. Each one only hands off to a normal Android app via an Intent; the user finishes it there. */
object Actions {
    fun describe(a: Action): String = when (a.name) {
        "open_app" -> "App kholna: ${a.args.optString("name")}"
        "set_timer" -> "Timer lagana: ${a.args.optInt("seconds")} second"
        "set_alarm" -> "Alarm lagana: %02d:%02d".format(a.args.optInt("hour"), a.args.optInt("minute"))
        "web_search" -> "Search karna: ${a.args.optString("query")}"
        "dial" -> "Dialer kholna: ${a.args.optString("number")}"
        "send_sms" -> "SMS taiyar karna (${a.args.optString("number")}): ${a.args.optString("text")}"
        else -> "Anjaan kaam: ${a.name}"
    }

    /** Returns a plain-text outcome that is sent back to the model. Never claims more than what happened. */
    fun execute(ctx: Context, a: Action): String = try {
        when (a.name) {
            "open_app" -> openApp(ctx, a.args.optString("name"))
            "set_timer" -> start(ctx, Intent(AlarmClock.ACTION_SET_TIMER)
                .putExtra(AlarmClock.EXTRA_LENGTH, a.args.optInt("seconds"))
                .putExtra(AlarmClock.EXTRA_MESSAGE, a.args.optString("label", "JARVIS"))
                .putExtra(AlarmClock.EXTRA_SKIP_UI, true), "Timer set kar diya gaya.")
            "set_alarm" -> start(ctx, Intent(AlarmClock.ACTION_SET_ALARM)
                .putExtra(AlarmClock.EXTRA_HOUR, a.args.optInt("hour"))
                .putExtra(AlarmClock.EXTRA_MINUTES, a.args.optInt("minute"))
                .putExtra(AlarmClock.EXTRA_MESSAGE, a.args.optString("label", "JARVIS"))
                .putExtra(AlarmClock.EXTRA_SKIP_UI, true), "Alarm set kar diya gaya.")
            "web_search" -> start(ctx, Intent(Intent.ACTION_VIEW,
                Uri.parse("https://www.google.com/search?q=" + Uri.encode(a.args.optString("query")))), "Search page khol diya.")
            "dial" -> start(ctx, Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + Uri.encode(a.args.optString("number")))),
                "Dialer khul gaya. Call user khud dabayega.")
            "send_sms" -> start(ctx, Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + Uri.encode(a.args.optString("number"))))
                .putExtra("sms_body", a.args.optString("text")), "Messages app khul gaya. Send user khud dabayega, abhi bheja nahi gaya.")
            else -> "ERROR: ye kaam supported nahi hai."
        }
    } catch (e: Exception) {
        "ERROR: ${e.javaClass.simpleName} ${e.message ?: ""}".trim()
    }

    private fun start(ctx: Context, i: Intent, ok: String): String {
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        ctx.startActivity(i)
        return ok
    }

    private fun openApp(ctx: Context, name: String): String {
        val pm = ctx.packageManager
        val main = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val hit = pm.queryIntentActivities(main, 0)
            .firstOrNull { it.loadLabel(pm).toString().contains(name, ignoreCase = true) }
            ?: return "ERROR: '$name' naam ka app nahi mila."
        val launch = pm.getLaunchIntentForPackage(hit.activityInfo.packageName)
            ?: return "ERROR: app khul nahi sakta."
        return start(ctx, launch, "${hit.loadLabel(pm)} khol diya.")
    }
}
