package com.google.mediapipe.examples.llminference.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// System monospace font — gives CLI/terminal feel without a bundled font file.
// On most Android devices this resolves to Droid Sans Mono or Roboto Mono.
val MonoFamily: FontFamily = FontFamily.Monospace

val RideTypography = Typography(
    // Data values — large monospace numbers (e.g. PHQ score)
    displaySmall = TextStyle(
        fontFamily  = MonoFamily,
        fontWeight  = FontWeight.Bold,
        fontSize    = 56.sp,
        lineHeight  = 64.sp,
        letterSpacing = 0.sp
    ),
    // Section headers
    titleLarge = TextStyle(
        fontFamily  = FontFamily.Default,
        fontWeight  = FontWeight.SemiBold,
        fontSize    = 16.sp,
        lineHeight  = 22.sp,
        letterSpacing = 0.15.sp
    ),
    titleMedium = TextStyle(
        fontFamily  = FontFamily.Default,
        fontWeight  = FontWeight.Medium,
        fontSize    = 13.sp,
        lineHeight  = 18.sp,
        letterSpacing = 0.1.sp
    ),
    // Body text
    bodyLarge = TextStyle(
        fontFamily  = FontFamily.Default,
        fontWeight  = FontWeight.Normal,
        fontSize    = 14.sp,
        lineHeight  = 20.sp,
        letterSpacing = 0.25.sp
    ),
    bodyMedium = TextStyle(
        fontFamily  = FontFamily.Default,
        fontWeight  = FontWeight.Normal,
        fontSize    = 12.sp,
        lineHeight  = 17.sp,
        letterSpacing = 0.25.sp
    ),
    // Monospace data rows — sensor values, timestamps, status tags
    labelLarge = TextStyle(
        fontFamily  = MonoFamily,
        fontWeight  = FontWeight.Medium,
        fontSize    = 12.sp,
        lineHeight  = 16.sp,
        letterSpacing = 0.sp
    ),
    labelMedium = TextStyle(
        fontFamily  = MonoFamily,
        fontWeight  = FontWeight.Normal,
        fontSize    = 11.sp,
        lineHeight  = 15.sp,
        letterSpacing = 0.sp
    ),
    labelSmall = TextStyle(
        fontFamily  = MonoFamily,
        fontWeight  = FontWeight.Normal,
        fontSize    = 10.sp,
        lineHeight  = 14.sp,
        letterSpacing = 0.sp
    ),
)
