package com.autolife.composeapp.platform

import android.Manifest
import android.content.ContentResolver
import android.content.Context
import android.content.pm.PackageManager
import android.provider.CallLog
import android.provider.Telephony
import androidx.core.content.ContextCompat
import java.util.Calendar

/**
 * Computes comm_reciprocity = outgoing / (outgoing + incoming) per day from
 * SMS messages and call logs.
 *
 * Requires READ_SMS and/or READ_CALL_LOG (dangerous runtime permissions).
 * Either permission alone is sufficient — the available source is used and
 * coverage reflects what was actually read. Returns null if neither is granted.
 *
 * StudentLife rationale: reciprocity near 0.5 indicates balanced social
 * exchange; skew toward 0 (only receiving) or 1 (only initiating) correlates
 * with social stress and isolation in the paper.
 */
internal object CommLogReader {

    data class CommMarkers(
        val reciprocity: Float,
        val coverage: Float,   // 1.0 = both SMS+calls, 0.5 = one source only
    )

    fun hasAnySmsPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.READ_SMS) ==
            PackageManager.PERMISSION_GRANTED

    fun hasCallLogPermission(context: Context): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CALL_LOG) ==
            PackageManager.PERMISSION_GRANTED

    fun computeForDay(context: Context, dayKey: String): CommMarkers? {
        val hasSms = hasAnySmsPermission(context)
        val hasCalls = hasCallLogPermission(context)
        if (!hasSms && !hasCalls) return null

        val (dayStart, dayEnd) = dayWindowMs(dayKey)

        var outgoing = 0
        var incoming = 0
        var sourcesAvailable = 0

        if (hasSms) {
            val (smsIn, smsOut) = querySms(context.contentResolver, dayStart, dayEnd)
            incoming += smsIn
            outgoing += smsOut
            sourcesAvailable++
        }

        if (hasCalls) {
            val (callsIn, callsOut) = queryCalls(context.contentResolver, dayStart, dayEnd)
            incoming += callsIn
            outgoing += callsOut
            sourcesAvailable++
        }

        val total = outgoing + incoming
        if (total == 0) return null   // no communication recorded; skip rather than emit 0

        return CommMarkers(
            reciprocity = outgoing.toFloat() / total,
            coverage = sourcesAvailable / 2f,
        )
    }

    private fun querySms(cr: ContentResolver, start: Long, end: Long): Pair<Int, Int> {
        var inbox = 0
        var sent = 0
        runCatching {
            val selection = "${Telephony.Sms.DATE} >= ? AND ${Telephony.Sms.DATE} < ?"
            cr.query(
                Telephony.Sms.CONTENT_URI,
                arrayOf(Telephony.Sms.TYPE),
                selection,
                arrayOf(start.toString(), end.toString()),
                null,
            )?.use { cursor ->
                val col = cursor.getColumnIndexOrThrow(Telephony.Sms.TYPE)
                while (cursor.moveToNext()) {
                    when (cursor.getInt(col)) {
                        Telephony.Sms.MESSAGE_TYPE_INBOX -> inbox++
                        Telephony.Sms.MESSAGE_TYPE_SENT  -> sent++
                    }
                }
            }
        }
        return Pair(inbox, sent)
    }

    private fun queryCalls(cr: ContentResolver, start: Long, end: Long): Pair<Int, Int> {
        var incoming = 0
        var outgoing = 0
        runCatching {
            val selection = "${CallLog.Calls.DATE} >= ? AND ${CallLog.Calls.DATE} < ?"
            cr.query(
                CallLog.Calls.CONTENT_URI,
                arrayOf(CallLog.Calls.TYPE),
                selection,
                arrayOf(start.toString(), end.toString()),
                null,
            )?.use { cursor ->
                val col = cursor.getColumnIndexOrThrow(CallLog.Calls.TYPE)
                while (cursor.moveToNext()) {
                    when (cursor.getInt(col)) {
                        CallLog.Calls.INCOMING_TYPE -> incoming++  // answered only
                        CallLog.Calls.OUTGOING_TYPE -> outgoing++
                        // MISSED_TYPE (3), REJECTED_TYPE (5) — not counted
                    }
                }
            }
        }
        return Pair(incoming, outgoing)
    }

    private fun dayWindowMs(dayKey: String): Pair<Long, Long> {
        val parts = dayKey.split("-")
        val cal = Calendar.getInstance()
        cal.set(parts[0].toInt(), parts[1].toInt() - 1, parts[2].toInt(), 0, 0, 0)
        cal.set(Calendar.MILLISECOND, 0)
        val start = cal.timeInMillis
        return Pair(start, start + 24L * 60 * 60 * 1000)
    }
}
