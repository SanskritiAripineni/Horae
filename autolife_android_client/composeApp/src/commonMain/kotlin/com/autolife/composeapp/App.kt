package com.autolife.composeapp

import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import com.autolife.composeapp.ui.AutoLifeNavHost
import com.autolife.composeapp.ui.screens.ConsentScreen
import com.autolife.composeapp.ui.theme.AutoLifeTheme
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.platform.currentTimeMillis

@Composable
fun AutoLifeApp(
    onServiceToggle: (Boolean) -> Unit = {},
    onDecline: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    var consented by remember { mutableStateOf(DatabaseRepository.hasConsented()) }

    AutoLifeTheme {
        if (consented) {
            AutoLifeNavHost(
                onServiceToggle = onServiceToggle,
                modifier = modifier,
            )
        } else {
            ConsentScreen(
                onConsented = {
                    DatabaseRepository.recordConsent(consentedAt = currentTimeMillis())
                    consented = true
                },
                onDeclined = onDecline,
            )
        }
    }
}
