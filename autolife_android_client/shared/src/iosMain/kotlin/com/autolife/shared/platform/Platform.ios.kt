package com.autolife.shared.platform

import platform.Foundation.NSDate
import platform.Foundation.NSCalendar
import platform.Foundation.timeIntervalSince1970

actual fun currentTimeMillis(): Long =
    (NSDate().timeIntervalSince1970 * 1000).toLong()

actual fun currentTimeZoneId(): String = NSCalendar.currentCalendar.timeZone.name
