plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "com.humanaize.aizecompanion"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.humanaize.aizecompanion"
        minSdk = 24
        targetSdk = 34
        // versionCode 格式：主版本×10000 + 次版本×100 + 修订版本
        // 2.2.7 → 20207，与系统版本号同步
        versionCode = 20207
        versionName = "2.2.7"
        
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    signingConfigs {
        create("release") {
            // Use debug keystore for now - replace with real keystore for production
            storeFile = file("../keystore/debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
            // 明確啟用 v1/v2/v3 簽名方案，確保在 HyperOS / 小米設備上正常安裝
            enableV1Signing = true
            enableV2Signing = true
            enableV3Signing = true
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            signingConfig = signingConfigs.getByName("release")
        }
        debug {
            isDebuggable = true
            applicationIdSuffix = ".debug"
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    
    kotlinOptions {
        jvmTarget = "17"
    }
    
    buildFeatures {
        compose = true
        buildConfig = true
    }
    
    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.5"
    }
}

dependencies {
    // AndroidX Core
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.6.2")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.6.2")
    
    // Material Components for XML themes
    implementation("com.google.android.material:material:1.11.0")
    
    // Compose
    implementation(platform("androidx.compose:compose-bom:2023.10.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.navigation:navigation-compose:2.7.5")
    
    // DataStore for preferences
    implementation("androidx.datastore:datastore-preferences:1.0.0")
    
    // Serialization
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.2")
    
    // OkHttp for WebSocket
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    
    // Coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3")
    
    // WorkManager for background tasks
    implementation("androidx.work:work-runtime-ktx:2.9.0")
    
    // Shizuku API - 用於獲取 Shell (adb) 級別權限
    implementation("dev.rikka.shizuku:api:13.1.5")
    implementation("dev.rikka.shizuku:provider:13.1.5")
    
    // Debug
    debugImplementation("androidx.compose.ui:ui-tooling")
}
