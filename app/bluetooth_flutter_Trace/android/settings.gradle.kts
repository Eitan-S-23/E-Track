// android/settings.gradle.kts
pluginManagement {
    // 1. 关键：在 pluginManagement 内部直接读取 flutter.sdk（与成功项目逻辑一致）
    val flutterSdkPath = run {
        val properties = java.util.Properties()
        val localPropertiesFile = file("local.properties")
        check(localPropertiesFile.exists()) {
            "❌ local.properties 不存在，请在 android 目录新建该文件，并添加 flutter.sdk=你的FlutterSDK路径"
        }
        localPropertiesFile.inputStream().use { properties.load(it) }
        val path = properties.getProperty("flutter.sdk")
        require(path != null) { "❌ local.properties 中未配置 flutter.sdk，请添加：flutter.sdk=D:/你的/Flutter/路径" }
        path
    }

    // 2. 引入 Flutter 工具链的 Gradle 构建（使用内部定义的 flutterSdkPath，无作用域问题）
    includeBuild("$flutterSdkPath/packages/flutter_tools/gradle")

    // 3. 插件仓库配置（与成功项目一致）
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

// 4. 全局插件版本管理（与成功项目完全一致）
plugins {
    id("dev.flutter.flutter-plugin-loader") version "1.0.0"
    id("com.android.application") version "8.9.1" apply false
    id("org.jetbrains.kotlin.android") version "2.1.0" apply false
}

// 5. 包含 app 模块（保留原有逻辑）
include(":app")

// 6. 移除外部调试打印（避免引用内部变量导致报错，如需调试可在 pluginManagement 内部打印）
// （可选）内部调试打印（在 pluginManagement 内添加，构建后可删除）
// println("✅ Flutter SDK 路径加载成功：$flutterSdkPath")