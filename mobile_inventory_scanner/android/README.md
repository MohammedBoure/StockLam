# Mobile Inventory Scanner - Android Host Configuration

Android platform configuration and Gradle project files for the Flutter companion app.

## Files & Directories

- pp/: Android application module containing AndroidManifest.xml, build configuration, Kotlin sources, Proguard rules, and mipmap resources.
- pp/proguard-rules.pro: R8/ProGuard shrinking and obfuscation rules for release builds.
- gradle/: Gradle wrapper binaries and properties.
- uild.gradle.kts: Root Gradle build script configuring repository sources and Kotlin DSL plugin resolution.
- gradle.properties: Gradle JVM daemon and memory settings.
- gradlew / gradlew.bat: Unix and Windows Gradle wrapper execution scripts.
- settings.gradle.kts: Gradle project inclusion and plugin resolution configuration.
