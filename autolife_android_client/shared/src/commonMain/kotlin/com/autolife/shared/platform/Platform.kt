package com.autolife.shared.platform

/** Returns the current epoch time in milliseconds. */
expect fun currentTimeMillis(): Long

/** Returns the device's current IANA timezone id, e.g. America/Phoenix. */
expect fun currentTimeZoneId(): String
