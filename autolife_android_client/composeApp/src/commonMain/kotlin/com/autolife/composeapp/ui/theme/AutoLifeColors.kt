package com.autolife.composeapp.ui.theme

import androidx.compose.ui.graphics.Color

// Light mode — iOS-inspired system colors
object AutoLifeLight {
    val background       = Color(0xFFF2F2F7)
    val surface          = Color(0xFFFFFFFF)
    val surfaceSecondary = Color(0xFFF2F2F7)
    val onBackground     = Color(0xFF1C1C1E)
    val onSurface        = Color(0xFF1C1C1E)
    val onSurfaceDim     = Color(0xFF8E8E93)
    val outline          = Color(0xFFD1D1D6)

    val primary          = Color(0xFF007AFF)
    val onPrimary        = Color(0xFFFFFFFF)
    val secondary        = Color(0xFF34C759)
    val tertiary         = Color(0xFFFF9500)
    val error            = Color(0xFFFF3B30)
}

// Dark mode
object AutoLifeDark {
    val background       = Color(0xFF000000)
    val surface          = Color(0xFF1C1C1E)
    val surfaceSecondary = Color(0xFF2C2C2E)
    val onBackground     = Color(0xFFFFFFFF)
    val onSurface        = Color(0xFFFFFFFF)
    val onSurfaceDim     = Color(0xFF8E8E93)
    val outline          = Color(0xFF38383A)

    val primary          = Color(0xFF0A84FF)
    val onPrimary        = Color(0xFFFFFFFF)
    val secondary        = Color(0xFF30D158)
    val tertiary         = Color(0xFFFF9F0A)
    val error            = Color(0xFFFF453A)
}

// Semantic colors — risk levels, categories, tools
object AutoLifeSemantic {
    val riskLow          = Color(0xFF34C759)
    val riskMild         = Color(0xFFFF9500)
    val riskModerate     = Color(0xFFFF6B00)
    val riskSevere       = Color(0xFFFF3B30)

    val categoryWork     = Color(0xFF007AFF)
    val categoryHealth   = Color(0xFF34C759)
    val categoryLeisure  = Color(0xFFFFCC00)

    val toolAutoLife     = Color(0xFFFF9500)
    val toolKEmo         = Color(0xFFFF3B30)
    val toolVectorDB     = Color(0xFF5AC8FA)
    val toolCalendar     = Color(0xFF34C759)

    fun riskColor(level: String?): Color = when (level?.lowercase()) {
        "low"      -> riskLow
        "mild"     -> riskMild
        "moderate" -> riskModerate
        "severe", "high" -> riskSevere
        else       -> riskLow
    }
}
