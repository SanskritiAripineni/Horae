package com.autolife.composeapp

import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import com.autolife.composeapp.ui.AutoLifeNavHost
import com.autolife.composeapp.ui.screens.ConsentScreen
import com.autolife.composeapp.ui.theme.AutoLifeTheme
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.EnrollRequest
import com.autolife.shared.network.AutoLifeApi
import com.autolife.shared.platform.currentTimeMillis
import kotlinx.coroutines.launch

@Composable
fun AutoLifeApp(
    onServiceToggle: (Boolean) -> Unit = {},
    onDecline: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    var consented by remember { mutableStateOf(DatabaseRepository.hasConsented()) }
    val scope = rememberCoroutineScope()

    // Restore stored auth token into the API client on startup
    LaunchedEffect(Unit) {
        DatabaseRepository.getAuthToken()?.let { token ->
            AutoLifeApi.setAuthToken(token)
        }
    }

    AutoLifeTheme {
        if (consented) {
            AutoLifeNavHost(
                onServiceToggle = onServiceToggle,
                modifier = modifier,
            )
        } else {
            ConsentScreen(
                onConsented = {
                    val now = currentTimeMillis()
                    DatabaseRepository.recordConsent(consentedAt = now)
                    consented = true
                    scope.launch {
                        try {
                            val resp = AutoLifeApi.enroll(EnrollRequest(consented_at = now))
                            resp.auth_token?.let { token ->
                                DatabaseRepository.saveAuthToken(token)
                                AutoLifeApi.setAuthToken(token)
                            }
                        } catch (_: Exception) {
                            // Enrollment failure is non-fatal — consent is recorded locally
                        }
                    }
                },
                onDeclined = onDecline,
            )
        }
    }
}
