// android/build.gradle.kts
import org.gradle.api.tasks.Delete
import org.gradle.api.file.Directory

// 1. 所有子项目的仓库配置（与成功项目一致）
allprojects {
    repositories {
        google()
        mavenCentral()
    }
}

// 2. 配置 rootProject 构建目录（与成功项目一致：指向 Flutter 根目录的 build 文件夹）
val newBuildDir: Directory =
    rootProject.layout.buildDirectory
        .dir("../../build")
        .get()
rootProject.layout.buildDirectory.value(newBuildDir)

// 3. 配置子项目构建目录（与成功项目一致：rootProject.buildDir/子项目名）
subprojects {
    val newSubprojectBuildDir: Directory = newBuildDir.dir(project.name)
    project.layout.buildDirectory.value(newSubprojectBuildDir)
}

// 4. 子项目依赖评估（与成功项目一致）
subprojects {
    project.evaluationDependsOn(":app")
}

// 5. 清理任务（与成功项目一致）
tasks.register<Delete>("clean") {
    delete(rootProject.layout.buildDirectory)
}