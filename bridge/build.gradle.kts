plugins {
    alias(libs.plugins.fabric.loom)
    `java-library`
}

group = "org.minekin"
version = providers.gradleProperty("mod_version").get()

base {
    archivesName = "minekin-bridge"
}

dependencies {
    minecraft(libs.minecraft)
    mappings(variantOf(libs.yarn) { classifier("v2") })
    modImplementation(libs.fabric.loader)
    modImplementation(libs.fabric.api)
    testImplementation(platform(libs.junit.bom))
    testImplementation(libs.junit.jupiter)
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

java {
    toolchain.languageVersion = JavaLanguageVersion.of(21)
    withSourcesJar()
}

tasks.withType<JavaCompile>().configureEach {
    options.release = 21
    options.encoding = "UTF-8"
}

tasks.test {
    useJUnitPlatform()
}

dependencyLocking {
    lockAllConfigurations()
}
