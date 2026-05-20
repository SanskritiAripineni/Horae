plugins {
    alias(libs.plugins.kotlin.multiplatform)
    alias(libs.plugins.android.kotlin.multiplatform.library)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.sqldelight)
}

kotlin {
    android {
        namespace = "com.autolife.shared"
        compileSdk = 35
        minSdk = 24
        compilerOptions {
            jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
        }
    }

    listOf(
        iosX64(),
        iosArm64(),
        iosSimulatorArm64()
    ).forEach { iosTarget ->
        iosTarget.binaries.framework {
            baseName = "Shared"
            isStatic = true
        }
    }

    sourceSets {
        commonMain.dependencies {
            api(libs.kotlinx.serialization.json)
            api(libs.kotlinx.coroutines.core)
            api(libs.ktor.client.core)
            api(libs.ktor.client.content.negotiation)
            api(libs.ktor.serialization.kotlinx.json)
            api(libs.ktor.client.logging)
            api(libs.sqldelight.runtime)
            api(libs.sqldelight.coroutines)
        }
        androidMain.dependencies {
            api(libs.ktor.client.okhttp)
            api(libs.sqldelight.android.driver)
        }
        iosMain.dependencies {
            api(libs.ktor.client.darwin)
            api(libs.sqldelight.native.driver)
        }
    }
}

sqldelight {
    databases {
        create("AutoLifeDatabase") {
            packageName.set("com.autolife.shared.db")
        }
    }
}
