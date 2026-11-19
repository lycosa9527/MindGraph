import java.util.Properties

plugins {
    id("com.android.application")
}

val glassesVersion = Properties().apply {
    rootProject.file("version.properties").inputStream().use { load(it) }
}

val localEndpoint = Properties().apply {
    val file = rootProject.file("local-endpoint.properties")
    if (file.exists()) {
        file.inputStream().use { load(it) }
    }
}
val localHost = localEndpoint.getProperty("LOCAL_HOST")?.trim().orEmpty().ifEmpty { "127.0.0.1" }

android {
    namespace = "com.mindgraph.glasssheet"
    compileSdk {
        version = release(37) {
            minorApiLevel = 0
        }
    }

    defaultConfig {
        applicationId = "com.mindgraph.glasssheet"
        minSdk = 31
        targetSdk = 37
        versionCode = glassesVersion.getProperty("VERSION_CODE").trim().toInt()
        versionName = glassesVersion.getProperty("VERSION_NAME").trim()
        buildConfigField(
            "String",
            "INGEST_URL",
            "\"http://$localHost:9527/api/learning-space/glasses/ingest\"",
        )
    }

    buildFeatures {
        buildConfig = true
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.16.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.camera:camera-core:1.4.2")
    implementation("androidx.camera:camera-camera2:1.4.2")
    implementation("androidx.camera:camera-lifecycle:1.4.2")
    implementation("com.google.zxing:core:3.5.3")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    testImplementation("junit:junit:4.13.2")
}
