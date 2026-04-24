package com.autolife.composeapp.ui

/**
 * Simple cross-platform date formatting from epoch millis.
 * Avoids java.text.SimpleDateFormat which is Android-only.
 */
object DateFormat {
    private val MONTHS = arrayOf(
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
    )

    /** Format as "Jan 5  14:30" */
    fun dateTime(epochMs: Long): String {
        val parts = epochToParts(epochMs)
        return "${MONTHS[parts.month]} ${parts.day}  ${pad2(parts.hour)}:${pad2(parts.minute)}"
    }

    /** Format as "14:30" */
    fun time(epochMs: Long): String {
        val parts = epochToParts(epochMs)
        return "${pad2(parts.hour)}:${pad2(parts.minute)}"
    }

    /** Format as "Apr 22, 2025" */
    fun monthDayYear(epochMs: Long): String {
        val parts = epochToParts(epochMs)
        return "${MONTHS[parts.month]} ${parts.day}, ${parts.year}"
    }

    private fun pad2(n: Int): String = if (n < 10) "0$n" else "$n"

    private data class DateParts(
        val year: Int, val month: Int, val day: Int,
        val hour: Int, val minute: Int, val second: Int
    )

    private fun epochToParts(epochMs: Long): DateParts {
        // Simple epoch-to-date conversion (assumes local timezone ≈ UTC for display)
        val totalSeconds = epochMs / 1000
        val totalDays = (totalSeconds / 86400).toInt()
        val timeOfDay = (totalSeconds % 86400).toInt()

        val hour = timeOfDay / 3600
        val minute = (timeOfDay % 3600) / 60
        val second = timeOfDay % 60

        // Days since 1970-01-01
        var y = 1970
        var remaining = totalDays
        while (true) {
            val daysInYear = if (isLeapYear(y)) 366 else 365
            if (remaining < daysInYear) break
            remaining -= daysInYear
            y++
        }

        val monthDays = if (isLeapYear(y))
            intArrayOf(31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
        else
            intArrayOf(31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

        var m = 0
        while (m < 12 && remaining >= monthDays[m]) {
            remaining -= monthDays[m]
            m++
        }

        return DateParts(y, m, remaining + 1, hour, minute, second)
    }

    private fun isLeapYear(y: Int) = (y % 4 == 0 && y % 100 != 0) || (y % 400 == 0)

    /** "3.1" — one decimal place */
    fun fmtFloat1(f: Double): String {
        val rounded = (f * 10 + 0.5).toLong()
        return "${rounded / 10}.${rounded % 10}"
    }

    fun fmtFloat1(f: Float): String = fmtFloat1(f.toDouble())

    /** "3.14" — two decimal places */
    fun fmtFloat2(f: Double): String {
        val rounded = (f * 100 + 0.5).toLong()
        return "${rounded / 100}.${pad2((rounded % 100).toInt())}"
    }

    /** "3.141" — three decimal places */
    fun fmtFloat3(f: Double): String {
        val rounded = (f * 1000 + 0.5).toLong()
        val frac = (rounded % 1000).toInt()
        val fracStr = when {
            frac < 10 -> "00$frac"
            frac < 100 -> "0$frac"
            else -> "$frac"
        }
        return "${rounded / 1000}.$fracStr"
    }
}
