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
                body = "App studies how AI-assisted life summaries and scheduling suggestions may relate to wellbeing, stress, and daily routines. You are being invited to participate because you are 18 or older and use a smartphone regularly."
            )

            // Data collected
            ConsentSection(
                title = "What data is collected?",
                body = "With your consent and permissions, the app may collect:\n\n" +
                    "• Motion patterns — to estimate activity such as walking or being stationary\n" +
                    "• Location context — used to understand general place-based routines\n" +
                    "• WiFi network names — used to infer home, work, or other repeated contexts\n" +
                    "• Calendar events — read-only access used for schedule suggestions\n" +
                    "• Life journals — narrative summaries generated from recent context\n\n" +
                    "The app summarizes recent context and sends the information needed for journal generation to Gemini. Generated journals and study usage data may be sent to the App backend for research storage and analysis."
            )

            // Permissions
            ConsentSection(
                title = "If you deny permissions",
                body = "You can deny or revoke phone permissions at any time in system settings. When a permission is denied, App will not collect that category of data, and related journals or schedule suggestions may be missing, less detailed, or unavailable. Denying permissions does not enroll you in additional collection, and you can still leave the study by uninstalling the app or contacting the research team."
            )

            // How it's stored
            ConsentSection(
                title = "How is your data stored?",
                body = "Your study data is associated with a random user ID that is hashed before storage. Journals, wellbeing assessments, and related study records are stored on the App backend hosted in Railway cloud. Data is retained for the duration of the study (up to 12 months) and then deleted."
            )

            // Risks and benefits
            ConsentSection(
                title = "Risks and benefits",
                body = "Risks: Minimal. Some battery usage from background sensor collection. You may find AI-generated journal summaries occasionally inaccurate.\n\n" +
                    "Benefits: Personalized schedule insights and wellbeing feedback at no cost. Contribution to research on AI-assisted wellbeing and daily planning."
            )

            // Withdrawal
            ConsentSection(
                title = "Your rights",
                body = "Participation is entirely voluntary. You may withdraw at any time by uninstalling the app — no penalty or loss of benefits. You can also request deletion of your data by contacting the research team."
            )

            // Contact
            ConsentSection(
                title = "Contact",
                body = "App Research Team\nEmail: autolife.study@gmail.com\n\nIf you have concerns about your rights as a research participant, contact your institution's IRB office."
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
