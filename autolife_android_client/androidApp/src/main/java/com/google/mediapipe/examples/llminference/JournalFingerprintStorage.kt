package com.google.mediapipe.examples.llminference

import android.content.Context
import java.io.File

class JournalFingerprintStorage(context: Context) {
    private val file = File(context.filesDir, "last_journal_fingerprint.txt")

    fun get(): String? = file.takeIf { it.exists() }?.readText()?.takeIf { it.isNotBlank() }

    fun set(value: String) {
        file.writeText(value)
    }
}
