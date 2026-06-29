package com.autolife.shared.platform

import java.util.TimeZone

actual fun currentTimeMillis(): Long = System.currentTimeMillis()

actual fun currentTimeZoneId(): String = TimeZone.getDefault().id
