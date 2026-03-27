package com.google.mediapipe.examples.llminference.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.google.mediapipe.examples.llminference.data.AnalysisRepository
import com.google.mediapipe.examples.llminference.network.Recommendation
import com.google.mediapipe.examples.llminference.ui.theme.*

@Composable
fun HealthScreen() {
    val result by AnalysisRepository.result.collectAsStateWithLifecycle()

    if (result == null) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(DarkBackground),
            contentAlignment = Alignment.Center
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Text(
                    "NO DATA",
                    style = MaterialTheme.typography.titleLarge,
                    color = DarkOnSurfaceDim
                )
                Spacer(modifier = Modifier.height(8.dp))
                Text(
                    "Run analysis from the AGENT tab.",
                    style = MaterialTheme.typography.labelMedium,
                    color = DarkOnSurfaceDim
                )
            }
        }
        return
    }

    val mh = result!!.mental_health
    val phq4 = mh?.estimated_phq4 ?: 0
    val riskLevel = mh?.risk_level ?: "unknown"
    val rc = riskColor(riskLevel)

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(DarkBackground)
            .padding(horizontal = 12.dp),
        contentPadding = PaddingValues(vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        // ── PHQ-4 hero card ──────────────────────────────────
        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(2.dp),
                colors = CardDefaults.cardColors(containerColor = DarkSurface),
                border = BorderStroke(1.dp, rc)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        "MENTAL HEALTH ASSESSMENT",
                        style = MaterialTheme.typography.labelMedium,
                        color = DarkOnSurfaceDim
                    )
                    Text(
                        "source: K-Emo Phone / Journal Analysis",
                        style = MaterialTheme.typography.labelSmall,
                        color = DarkOnSurfaceDim
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.Bottom) {
                        Text(
                            phq4.toString().padStart(2, '0'),
                            style = MaterialTheme.typography.displaySmall,
                            color = rc
                        )
                        Text(
                            " / 12",
                            style = MaterialTheme.typography.titleLarge,
                            color = DarkOnSurfaceDim,
                            modifier = Modifier.padding(bottom = 6.dp)
                        )
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    LinearProgressIndicator(
                        progress = { phq4 / 12f },
                        modifier = Modifier.fillMaxWidth(),
                        color = rc,
                        trackColor = DarkBorder
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween
                    ) {
                        Text(
                            "risk_level: [${riskLevel.uppercase()}]",
                            style = MaterialTheme.typography.labelLarge,
                            color = rc
                        )
                        Text(
                            "PHQ-4",
                            style = MaterialTheme.typography.labelSmall,
                            color = DarkOnSurfaceDim
                        )
                    }
                }
            }
        }

        // ── Journal summary ──────────────────────────────────
        if (!result!!.journal_summary.isNullOrBlank()) {
            item {
                SectionHeader("JOURNAL SUMMARY")
                TerminalCard(accentColor = TerminalCyan) {
                    Text(
                        result!!.journal_summary!!,
                        style = MaterialTheme.typography.bodyMedium,
                        color = DarkOnSurface
                    )
                }
            }
        }

        // ── Key concerns ─────────────────────────────────────
        if (!mh?.key_concerns.isNullOrEmpty()) {
            item {
                SectionHeader("KEY CONCERNS")
                TerminalCard(accentColor = TerminalRed) {
                    mh!!.key_concerns.forEach { concern ->
                        Row(modifier = Modifier.padding(vertical = 2.dp)) {
                            Text(
                                "• ",
                                style = MaterialTheme.typography.labelMedium,
                                color = TerminalRed
                            )
                            Text(
                                concern,
                                style = MaterialTheme.typography.bodyMedium,
                                color = DarkOnSurface
                            )
                        }
                    }
                }
            }
        }

        // ── Positive indicators ──────────────────────────────
        if (!mh?.positive_indicators.isNullOrEmpty()) {
            item {
                SectionHeader("POSITIVE INDICATORS")
                TerminalCard(accentColor = TerminalGreen) {
                    mh!!.positive_indicators.forEach { pos ->
                        Row(modifier = Modifier.padding(vertical = 2.dp)) {
                            Text(
                                "+ ",
                                style = MaterialTheme.typography.labelMedium,
                                color = TerminalGreen
                            )
                            Text(
                                pos,
                                style = MaterialTheme.typography.bodyMedium,
                                color = DarkOnSurface
                            )
                        }
                    }
                }
            }
        }

        // ── Recommendations ──────────────────────────────────
        if (result!!.recommendations.isNotEmpty()) {
            item { SectionHeader("RECOMMENDATIONS") }
            items(result!!.recommendations) { rec ->
                RecommendationCard(rec)
            }
        }

        // ── Errors ───────────────────────────────────────────
        if (result!!.errors.isNotEmpty()) {
            item { SectionHeader("ERRORS") }
            items(result!!.errors) { err ->
                TerminalCard(accentColor = TerminalRed) {
                    Text(err, style = MaterialTheme.typography.labelMedium, color = TerminalRed)
                }
            }
        }
    }
}

@Composable
private fun RecommendationCard(rec: Recommendation) {
    val priorityColor = when (rec.priority?.lowercase()) {
        "high"   -> TerminalRed
        "medium" -> TerminalAmber
        "low"    -> TerminalGreen
        else     -> DarkOnSurfaceDim
    }
    TerminalCard(accentColor = priorityColor) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                "[${rec.category.uppercase()}]",
                style = MaterialTheme.typography.labelLarge,
                color = TerminalCyan,
                fontWeight = FontWeight.Bold
            )
            if (rec.priority != null) {
                Text(
                    rec.priority.uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    color = priorityColor
                )
            }
        }
        Spacer(modifier = Modifier.height(4.dp))
        Text(rec.action, style = MaterialTheme.typography.bodyMedium, color = DarkOnSurface)
        if (rec.when_to_do != null) {
            Spacer(modifier = Modifier.height(2.dp))
            Text(
                "when: ${rec.when_to_do}",
                style = MaterialTheme.typography.labelSmall,
                color = DarkOnSurfaceDim
            )
        }
    }
}
