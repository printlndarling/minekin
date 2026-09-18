pluginManagement {
    repositories {
        maven("https://maven.fabricmc.net/") { name = "Fabric" }
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    // Loom adds a local remapped-mod repository while configuring the project.
    repositoriesMode.set(RepositoriesMode.PREFER_PROJECT)
    repositories {
        maven("https://maven.fabricmc.net/") { name = "Fabric" }
        mavenCentral()
    }
}

rootProject.name = "minekin-bridge"
