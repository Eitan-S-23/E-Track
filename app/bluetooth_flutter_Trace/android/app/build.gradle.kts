// android/app/build.gradle.kts
import java.util.Properties

plugins {
    id("com.android.application")
    id("kotlin-android")
    id("dev.flutter.flutter-gradle-plugin")
}

val keystorePropertiesFile = rootProject.file("key.properties")
val keystoreProperties = Properties().apply {
    if (keystorePropertiesFile.exists()) {
        keystorePropertiesFile.inputStream().use { load(it) }
    }
}

fun signingProperty(name: String, vararg envNames: String): String? {
    keystoreProperties.getProperty(name)?.takeIf { it.isNotBlank() }?.let { return it }
    return envNames.asSequence()
        .mapNotNull { envName -> System.getenv(envName)?.takeIf { it.isNotBlank() } }
        .firstOrNull()
}

val releaseStoreFile = signingProperty("storeFile", "ANDROID_RELEASE_STORE_FILE", "SIDELOAD_STORE_FILE")
val releaseStorePassword =
    signingProperty("storePassword", "ANDROID_RELEASE_KEYSTORE_PASSWORD", "SIDELOAD_KEYSTORE_PASSWORD")
val releaseKeyAlias = signingProperty("keyAlias", "ANDROID_RELEASE_KEY_ALIAS", "SIDELOAD_KEY_ALIAS")
val releaseKeyPassword = signingProperty("keyPassword", "ANDROID_RELEASE_KEY_PASSWORD", "SIDELOAD_KEY_PASSWORD")
val releaseKeystoreFile = releaseStoreFile?.let { rootProject.file(it) }
val releaseSigningRequested =
    keystorePropertiesFile.exists() ||
        listOf(
            "ANDROID_RELEASE_STORE_FILE",
            "ANDROID_RELEASE_KEYSTORE_BASE64",
            "ANDROID_RELEASE_KEYSTORE_PASSWORD",
            "ANDROID_RELEASE_KEY_ALIAS",
            "ANDROID_RELEASE_KEY_PASSWORD",
            "SIDELOAD_STORE_FILE",
            "SIDELOAD_KEYSTORE_BASE64",
            "SIDELOAD_KEYSTORE_PASSWORD",
            "SIDELOAD_KEY_ALIAS",
            "SIDELOAD_KEY_PASSWORD",
        ).any { !System.getenv(it).isNullOrBlank() }
val hasReleaseSigningConfig =
    releaseKeystoreFile?.exists() == true &&
        !releaseStorePassword.isNullOrBlank() &&
        !releaseKeyAlias.isNullOrBlank() &&
        !releaseKeyPassword.isNullOrBlank()

if (releaseSigningRequested && !hasReleaseSigningConfig) {
    error(
        "Android release signing is incomplete. Provide android/key.properties with " +
            "storeFile, storePassword, keyAlias, keyPassword, or configure the fixed signing " +
            "GitHub Actions secrets and ensure the keystore file exists."
    )
}

android {
    namespace = "com.wen.gaia.gaia" // 替换为你的项目包名
    compileSdk = 35
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_11.toString()
    }

    defaultConfig {
        applicationId = "com.wen.gaia.gaia" // 替换为你的应用 ID
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
        ndk {
            abiFilters += setOf("armeabi-v7a", "arm64-v8a")
        }
    }

    signingConfigs {
        create("release") {
            if (hasReleaseSigningConfig) {
                storeFile = releaseKeystoreFile
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        getByName("release") {
            signingConfig = if (hasReleaseSigningConfig) {
                signingConfigs.getByName("release")
            } else {
                logger.warn(
                    "Android release signing is not configured; falling back to debug signing. " +
                        "Configure android/key.properties or fixed GitHub Actions secrets for reliable updates."
                )
                signingConfigs.getByName("debug")
            }
        }
    }

    packaging {
        jniLibs {
            excludes += setOf("lib/x86_64/**")
        }
    }
}

flutter {
    source = "../.." // 指向 Flutter 项目根目录（通常正确，无需修改）
}

dependencies {
    // Core library desugaring for flutter_local_notifications
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.0.4")
    implementation("androidx.core:core-ktx:1.13.1")
}
