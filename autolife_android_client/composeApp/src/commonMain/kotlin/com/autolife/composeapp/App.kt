package com.autolife.composeapp

import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import com.autolife.composeapp.ui.AutoLifeNavHost
import com.autolife.composeapp.ui.screens.ConsentScreen
import com.autolife.composeapp.ui.screens.NotEnrolledScreen
import com.autolife.composeapp.ui.theme.AutoLifeTheme
import com.autolife.shared.db.DatabaseRepository
import com.autolife.shared.model.EnrollRequest
import com.autolife.shared.network.AutoLifeApi
import com.autolife.shared.repository.AnalysisRepository
import com.autolife.shared.platform.currentTimeMillis
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.IO
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@OptIn(ExperimentalUuidApi::class)
private fun getOrCreateDeviceId(): String {
    val existing = DatabaseRepository.getDeviceId()
    if (existing != null) return existing
    val newId = Uuid.random().toString()
    DatabaseRepository.saveDeviceId(newId)
    return newId
}

@Composable
fun AutoLifeApp(
    onServiceToggle: (Boolean) -> Unit = {},
    onDecline: () -> Unit = {},
    onConsentReady: () -> Unit = {},
    modifier: Modifier = Modifier,
) {
    var consented by remember { mutableStateOf<Boolean?>(null) }
    var declined by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        val hasConsented = withContext(Dispatchers.IO) { DatabaseRepository.hasConsented() }
        consented = hasConsented
        if (hasConsented) onConsentReady()

        withContext(Dispatchers.IO) { DatabaseRepository.getAuthToken() }?.let { token ->
            AutoLifeApi.setAuthToken(token)
        }
        withContext(Dispatchers.IO) { DatabaseRepository.getDeviceId() }?.let { id ->
            AnalysisRepository.userId = id
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
                if (declined) {
                    NotEnrolledScreen()
                } else {
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
                                    val deviceId = getOrCreateDeviceId()
                                    AnalysisRepository.userId = deviceId
                                    val resp = AutoLifeApi.enroll(EnrollRequest(user_id = deviceId, consented_at = now))
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
                        onDeclined = {
                            declined = true
                            onDecline()
                        },
                    )
                }
            }
        }
    }
}
