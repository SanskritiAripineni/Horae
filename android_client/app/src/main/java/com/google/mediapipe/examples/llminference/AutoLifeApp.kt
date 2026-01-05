package com.google.mediapipe.examples.llminference

import android.app.Application
import com.google.mediapipe.examples.llminference.data.AppDatabase

class AutoLifeApp : Application() {
    val database by lazy { AppDatabase.getDatabase(this) }
}
