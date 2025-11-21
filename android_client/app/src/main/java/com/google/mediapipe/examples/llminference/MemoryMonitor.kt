package com.google.mediapipe.examples.llminference

import android.app.ActivityManager
import android.content.Context
import android.os.Debug
import android.util.Log

object MemoryMonitor {

    data class MemoryInfo(
        val usedMemoryMB: Long,
        val maxHeapSizeMB: Long,
        val nativeHeapMB: Long,
        val totalRSSMB: Long,
        val totalPSSMB: Long
    )

    fun getMemoryInfo(context: Context): MemoryInfo {
        // Java/Kotlin heap
        val runtime = Runtime.getRuntime()
        val used = (runtime.totalMemory() - runtime.freeMemory()) / (1024L * 1024L)
        val max = runtime.maxMemory() / (1024L * 1024L)

        // Native heap
        val nativeMb = Debug.getNativeHeapAllocatedSize() / (1024L * 1024L)

        // PSS/RSS from ActivityManager
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val pid = android.os.Process.myPid()
        val mi = am.getProcessMemoryInfo(intArrayOf(pid)).first()

        val pssMb = mi.totalPss.toLong() / 1024L     // in kB → MB
        val rssMb = mi.totalPrivateDirty.toLong() / 1024L // approx RSS

        val info = MemoryInfo(
            usedMemoryMB = used,
            maxHeapSizeMB = max,
            nativeHeapMB = nativeMb,
            totalRSSMB = rssMb,
            totalPSSMB = pssMb
        )
        Log.d("MemoryMonitor", "mem=$info")
        return info
    }
}
