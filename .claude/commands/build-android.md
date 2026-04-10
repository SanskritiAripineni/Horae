Build the Android app debug APK. Run from the autolife_android_client directory. If the build fails, read the error output carefully — common issues include KSP annotation processing failures and missing Ktor transitive dependencies.

Steps:
1. cd to autolife_android_client/
2. Run `./gradlew assembleDebug --stacktrace`
3. Report the result (success or failure with key error lines)
