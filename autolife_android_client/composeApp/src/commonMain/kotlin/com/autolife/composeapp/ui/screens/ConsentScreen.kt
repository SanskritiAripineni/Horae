package com.autolife.composeapp.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

@Composable
fun ConsentScreen(
    onConsented: () -> Unit,
    onDeclined: () -> Unit,
) {
    val scrollState = rememberScrollState()

    Scaffold { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(scrollState)
                .padding(horizontal = 24.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            // Header
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = "Research Study Consent",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.Bold,
                    textAlign = TextAlign.Center,
                )
                Text(
                    text = "RIDE — AI Life Scheduling Study",
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary,
                    textAlign = TextAlign.Center,
                )
            }

            HorizontalDivider()

            // Purpose
            ConsentSection(
                title = "What is this study?",
                body = "This research investigates how AI-optimized scheduling and personalized calendar suggestions affect mental wellbeing, stress, and daily productivity. You are being invited to participate because you are 18 or older and use a smartphone regularly."
            )

            // Data collected
            ConsentSection(
                title = "What data is collected?",
                body = "The app collects the following from your phone:\n\n" +
                    "• Motion patterns — to infer activity levels (walking, stationary, etc.)\n" +
                    "• Location context — generalised area only; raw GPS coordinates are never transmitted\n" +
                    "• WiFi network names — to infer home/work/other contexts\n" +
                    "• Life journals — AI-generated narrative summaries of your day (created on-device using Gemini)\n" +
                    "• Calendar events — read-only access to suggest schedule optimizations\n\n" +
                    "Raw sensor data (GPS, accelerometer) stays on your device. Only AI-generated journal summaries and anonymized usage data are sent to our server."
            )

            // How it's stored
            ConsentSection(
                title = "How is your data stored?",
                body = "Your data is identified by a random user ID that is SHA-256 hashed before storage — we cannot re-identify you from stored data. Journals and wellbeing assessments are stored on a secure server (Railway cloud). Data is retained for the duration of the study (up to 12 months) and then deleted."
            )

            // Risks and benefits
            ConsentSection(
                title = "Risks and benefits",
                body = "Risks: Minimal. Some battery usage from background sensor collection. You may find AI-generated journal summaries occasionally inaccurate.\n\n" +
                    "Benefits: Personalized schedule insights and wellbeing feedback at no cost. Contribution to research on AI-assisted mental wellness."
            )

            // Withdrawal
            ConsentSection(
                title = "Your rights",
                body = "Participation is entirely voluntary. You may withdraw at any time by uninstalling the app — no penalty or loss of benefits. You can also request deletion of your data by contacting the research team."
            )

            // Contact
            ConsentSection(
                title = "Contact",
                body = "AutoLife Research Team\nEmail: autolife.study@gmail.com\n\nIf you have concerns about your rights as a research participant, contact your institution's IRB office."
            )

            HorizontalDivider()

            // Agreement text
            Text(
                text = "By tapping \"I Agree\", you confirm that you have read and understood this consent form, that you are 18 or older, and that you voluntarily agree to participate in this study.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth(),
            )

            // Buttons
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Button(
                    onClick = onConsented,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("I Agree & Join Study")
                }
                OutlinedButton(
                    onClick = onDeclined,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Exit Without Joining")
                }
            }

            Spacer(modifier = Modifier.height(24.dp))
        }
    }
}

@Composable
private fun ConsentSection(title: String, body: String) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
        )
        Text(
            text = body,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}
