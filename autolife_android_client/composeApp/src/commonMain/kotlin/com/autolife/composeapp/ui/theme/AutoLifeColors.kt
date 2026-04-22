package com.autolife.composeapp.ui.theme

import androidx.compose.ui.graphics.Color

// Light mode - quiet wellness palette shared by Android and iOS
object AutoLifeLight {
    val background       = Color(0xFFFBFCF8)
    val surface          = Color(0xFFFFFFFF)
    val surfaceSecondary = Color(0xFFF2F5ED)
    val onBackground     = Color(0xFF25352D)
    val onSurface        = Color(0xFF25352D)
    val onSurfaceDim     = Color(0xFF69736D)
    val outline          = Color(0xFFE0E4DC)

    val primary          = Color(0xFF55744C)
    val primaryContainer = Color(0xFFE8EFE3)
    val onPrimaryContainer = Color(0xFF25352D)
    val onPrimary        = Color(0xFFFFFFFF)
    val secondary        = Color(0xFF4D815F)
    val secondaryContainer = Color(0xFFE6F0E8)
    val onSecondaryContainer = Color(0xFF25352D)
    val tertiary         = Color(0xFFC8802D)
    val tertiaryContainer = Color(0xFFF8E8D5)
    val onTertiaryContainer = Color(0xFF3A2710)
    val error            = Color(0xFFD85A4A)
    val errorContainer   = Color(0xFFFBE7E4)
    val onErrorContainer = Color(0xFF5E1710)
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
    val primaryContainer = Color(0xFF17324A)
    val onPrimaryContainer = Color(0xFFE7F1FF)
    val onPrimary        = Color(0xFFFFFFFF)
    val secondary        = Color(0xFF30D158)
    val secondaryContainer = Color(0xFF173820)
    val onSecondaryContainer = Color(0xFFE8F8EC)
    val tertiary         = Color(0xFFFF9F0A)
    val tertiaryContainer = Color(0xFF442B08)
    val onTertiaryContainer = Color(0xFFFFE9C8)
    val error            = Color(0xFFFF453A)
    val errorContainer   = Color(0xFF4A1714)
    val onErrorContainer = Color(0xFFFFE6E3)
}

// Semantic colors — risk levels, categories, tools
object AutoLifeSemantic {
    val riskLow          = Color(0xFF4D815F)
    val riskMild         = Color(0xFFC8802D)
    val riskModerate     = Color(0xFFB76B2B)
    val riskSevere       = Color(0xFFD85A4A)

    val categoryWork     = Color(0xFF8C95C8)
    val categoryHealth   = Color(0xFF6F8A64)
    val categoryLeisure  = Color(0xFFE7C77C)

    val toolAutoLife     = Color(0xFF6F8A64)
    val toolKEmo         = Color(0xFFC8802D)
    val toolVectorDB     = Color(0xFF7395A8)
    val toolCalendar     = Color(0xFF55744C)

    fun riskColor(level: String?): Color = when (level?.lowercase()) {
        "low", "minimal" -> riskLow
        "mild"           -> riskMild
        "moderate"       -> riskModerate
        "severe", "high" -> riskSevere
        else             -> riskLow
    }
}
