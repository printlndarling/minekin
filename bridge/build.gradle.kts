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
    // The test JVM inherits this project directory as its working directory, and
    // the Minecraft log4j configuration that the `minecraft(...)` dependency puts
    // on the test classpath writes `logs/latest.log` relative to it. That landed a
    // build artifact inside `bridge/`, which is the tree `source_tree_sha256`
    // hashes — so the recipe's `source_digest` depended on whether a build had run,
    // and a checked-out tree plus a build reported "Bridge source tree digest
    // differs from the bundle recipe" for a reason that had nothing to do with the
    // source. Build output belongs under `build/`, which the digest already
    // excludes.
    workingDir = layout.buildDirectory.dir("test-working-directory").get().asFile
    // Gradle does not create a test working directory, and a process cannot be
    // started in one that does not exist.
    doFirst { workingDir.mkdirs() }
}

dependencyLocking {
    lockAllConfigurations()
}
