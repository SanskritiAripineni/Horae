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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.IO
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun AutoLifeApp(
    onServiceToggle: (Boolean) -> Unit = {},
    onDecline: () -> Unit = {},
    onConsentReady: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    var consented by remember { mutableStateOf<Boolean?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        val hasConsented = withContext(Dispatchers.IO) { DatabaseRepository.hasConsented() }
        consented = hasConsented
        if (hasConsented) onConsentReady()

        withContext(Dispatchers.IO) { DatabaseRepository.getAuthToken() }?.let { token ->
            AutoLifeApi.setAuthToken(token)
        }
    }

    AutoLifeTheme {
        when (consented) {
            null -> Unit
            true -> {
                AutoLifeNavHost(
                    onServiceToggle = onServiceToggle,
                    modifier = modifier,
                )
            }
            false -> {
                ConsentScreen(
                    onConsented = {
                        val now = currentTimeMillis()
                        scope.launch {
                            withContext(Dispatchers.IO) {
                                DatabaseRepository.recordConsent(consentedAt = now)
                            }
                            consented = true
                            onConsentReady()
                            try {
                                val resp = AutoLifeApi.enroll(EnrollRequest(consented_at = now))
                                resp.auth_token?.let { token ->
                                    withContext(Dispatchers.IO) {
                                        DatabaseRepository.saveAuthToken(token)
                                    }
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
}
