plugins {
    alias(libs.plugins.fabric.loom)
    alias(libs.plugins.protobuf)
    `java-library`
}

group = "org.minekin"
// Captured here rather than read inside the task: this build enables Gradle's
// configuration cache, and reaching for `project.version` from a task action is
// exactly what that cache refuses.
val modVersion = providers.gradleProperty("mod_version").get()
version = modVersion

base {
    archivesName = "minekin-bridge"
}

dependencies {
    minecraft(libs.minecraft)
    mappings(variantOf(libs.yarn) { classifier("v2") })
    modImplementation(libs.fabric.loader)
    modImplementation(libs.fabric.api)
    implementation(libs.protobuf.javalite)
    include(libs.protobuf.javalite)
    testImplementation(platform(libs.junit.bom))
    testImplementation(libs.junit.jupiter)
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

sourceSets {
    main {
        proto {
            srcDir("../proto")
        }
    }
}

val protobufVersion = versionCatalogs.named("libs").findVersion("protobuf").get().requiredVersion

protobuf {
    protoc {
        artifact = "com.google.protobuf:protoc:$protobufVersion"
    }
    generateProtoTasks {
        all().configureEach {
            builtins {
                named("java") {
                    option("lite")
                }
            }
        }
    }
}

java {
    toolchain.languageVersion = JavaLanguageVersion.of(21)
    withSourcesJar()
}

// The mod's own metadata carries the version, and Fabric's template leaves a
// `${version}` placeholder for the build to fill in. Nothing filled it in, so
// the jar declared its version as the literal string "${version}" and the Loader
// warned about it on every launch: "Mod minekin_bridge uses the version
// ${version} which isn't compatible with Loader's extended semantic version
// format".
tasks.processResources {
    inputs.property("version", modVersion)
    // `expand` on the copy spec rather than inside a `filesMatching` closure:
    // this build enables the configuration cache, which cannot serialize the
    // closure Kotlin DSL would compile here. The resources are two text files.
    expand("version" to modVersion)
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
