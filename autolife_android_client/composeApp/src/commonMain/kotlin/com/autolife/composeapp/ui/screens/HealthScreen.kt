package com.autolife.composeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.autolife.composeapp.ui.components.*
import com.autolife.composeapp.ui.theme.AutoLifeSemantic
import com.autolife.shared.model.Recommendation
import com.autolife.shared.repository.AnalysisRepository

@Composable
fun HealthScreen() {
    val result by AnalysisRepository.result.collectAsState()
    val isLoading by AnalysisRepository.loading.collectAsState()

    if (result == null && isLoading) {
        Column(
            modifier = Modifier.fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            SkeletonCard(height = 140)
            SkeletonCard(height = 80)
            SkeletonCard(height = 160)
        }
        return
    }

    if (result == null) {
        EmptyState(
            icon = Icons.Default.FavoriteBorder,
            title = "No Health Data",
            description = "Run analysis from the Agent tab to see your wellbeing assessment.",
        )
        return
    }

    val mh = result!!.health
    val riskLevel = mh?.risk_level ?: "unknown"
    val rc = AutoLifeSemantic.riskColor(riskLevel)

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Wellbeing state hero card
        item {
            MetricCard(
                value = riskLevel.replaceFirstChar { it.uppercase() },
                label = "LLM-understood wellbeing state",
                color = rc,
            )
        }

        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                StatusPill(
                    text = riskLevel.replaceFirstChar { it.uppercase() },
                    color = rc,
                )
                Text(
                    text = "Wellbeing Assessment",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        if (!mh?.behavioral_context.isNullOrBlank()) {
            item {
                SectionHeader(title = "Behavioral Context")
                SurfaceCard {
                    Text(
                        text = mh!!.behavioral_context,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                }
            }
        }

        // Journal summary
        if (!result!!.journal_summary.isNullOrBlank()) {
            item {
                SectionHeader(title = "Summary")
                SurfaceCard {
                    Text(
                        text = result!!.journal_summary!!,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                }
            }
        }

        // Key concerns
        if (!mh?.key_concerns.isNullOrEmpty()) {
            item {
                SectionHeader(title = "Key Concerns")
                SurfaceCard {
                    mh!!.key_concerns.forEach { concern ->
                        IconBulletItem(
                            icon = Icons.Default.Warning,
                            text = concern,
                            iconTint = AutoLifeSemantic.riskSevere,
                        )
                    }
                }
            }
        }

        // Positive indicators
        if (!mh?.positive_indicators.isNullOrEmpty()) {
            item {
                SectionHeader(title = "Positive Indicators")
                SurfaceCard {
                    mh!!.positive_indicators.forEach { pos ->
                        IconBulletItem(
                            icon = Icons.Default.CheckCircle,
                            text = pos,
                            iconTint = AutoLifeSemantic.riskLow,
                        )
                    }
                }
            }
        }

        // Recommendations
        if (result!!.recommendations.isNotEmpty()) {
            item { SectionHeader(title = "Recommendations") }
            items(result!!.recommendations) { rec ->
                RecommendationCard(rec)
            }
        }

        // Errors
        if (result!!.errors.isNotEmpty()) {
            item { SectionHeader(title = "Errors") }
            items(result!!.errors) { err ->
                SurfaceCard {
                    Text(
                        text = err,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }
    }
}

@Composable
private fun RecommendationCard(rec: Recommendation) {
    val priorityColor = when (rec.priority?.lowercase()) {
        "high"   -> AutoLifeSemantic.riskSevere
        "medium" -> AutoLifeSemantic.riskMild
        "low"    -> AutoLifeSemantic.riskLow
        else     -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    SurfaceCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            StatusPill(
                text = rec.category.replaceFirstChar { it.uppercase() },
                color = MaterialTheme.colorScheme.primary,
            )
            if (rec.priority != null) {
                StatusPill(
                    text = rec.priority!!.replaceFirstChar { it.uppercase() },
                    color = priorityColor,
                )
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(
            text = rec.action,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface,
        )
        if (rec.when_to_do != null) {
            Spacer(Modifier.height(4.dp))
            Text(
                text = rec.when_to_do!!,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
