# JARVIS Android assistant (system assistant, like Gemini / Siri)

Ye asli Android app hai jo phone ka **Digital assistant** ban sakta hai. Power/side button long-press (ya home gesture hold) karte hi JARVIS ka panel khulta hai, tum bolte ho, wo sochta hai (Gemini), bolke jawab deta hai.

## Kya karta hai
- Hinglish / हिन्दी / English me sunna aur bolna.
- Gemini se baat (key sirf tumhare phone me save hoti hai).
- Phone ke kaam: app kholna, timer, alarm, web search, dialer kholna, SMS taiyar karna.
- **Har kaam se pehle tumse Haan/Nahi puchta hai.** Call aur SMS bhejna tum khud dabate ho; JARVIS khud call/SMS nahi karta.

## Kya NAHI karta (sach)
- "Hey Google"/"Hey JARVIS" jaisa hamesha-sunne wala shabd: Android third-party app ko ye allow nahi karta. Bulane ke liye button/gesture hi use hota hai.
- Doosre apps ke andar click/type nahi karta (isme Accessibility permission lagti hai; abhi nahi joda).
- Purane Termux wale tools (ffmpeg video edit, YouTube skills, client research) is app me nahi hain. Wo abhi alag Termux wale JARVIS me hain.
- Ye pehla version hai. **Mere paas phone ya Android SDK nahi tha, isliye ye abhi kisi phone par chala kar test nahi hua** aur pehli build me compile error aa sakta hai. Error aaye to GitHub Actions ka log bhejna, main theek kar dunga.

## APK kaise milega
1. GitHub repo me **Actions** tab > "Build JARVIS Android APK" > build hari ho (3-6 min).
2. Repo ke **Releases** (right side) me "JARVIS Android APK (latest build)" > `jarvis-assistant.apk` download karo.
3. Phone par APK kholo. "Install unknown apps" ki permission Chrome/Files ko do. Play Protect warning aaye to "Install anyway" (ye debug build hai, Play Store par nahi hai).

## Setup (ek baar)
1. JARVIS app kholo > Gemini key paste karo > bhasha chuno > **Save karo**.
2. **Mic permission do** dabao > Allow.
3. **Assistant settings kholo** > Digital assistant app = JARVIS.
4. Samsung: Settings > Advanced features > Side button > Press and hold = **Wake Digital assistant**.
5. Side button dabake rakho. JARVIS khulega, bolo.

## Developer notes
- Package `com.raido.jarvis`, minSdk 26, Kotlin, koi external library nahi.
- Key `SharedPreferences` (private) me; kabhi repo/log me nahi.
- Build: `cd jarvis/android && gradle assembleDebug` (Android SDK chahiye). CI ye apne aap karta hai.
